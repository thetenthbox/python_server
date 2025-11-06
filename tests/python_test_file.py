# --------------------------------------------------------------
# 0. Imports & Setup
# --------------------------------------------------------------
import os, json, warnings, random, itertools
from collections import Counter


import numpy as np, pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.decomposition import PCA
from sklearn.preprocessing import OneHotEncoder, StandardScaler, MultiLabelBinarizer
from sklearn.metrics import roc_auc_score


import nltk
nltk.download('vader_lexicon')
from nltk.sentiment.vader import SentimentIntensityAnalyzer


import lightgbm as lgb
from catboost import CatBoostClassifier, Pool


import torch
from transformers import AutoTokenizer, AutoModel


warnings.filterwarnings("ignore")
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)


# --------------------------------------------------------------
# 1. Load data
# --------------------------------------------------------------
DATA_PATH = "./data"
with open(os.path.join(DATA_PATH, "train.json")) as f:
    train_data = json.load(f)
with open(os.path.join(DATA_PATH, "test.json")) as f:
    test_data = json.load(f)


train_df = pd.DataFrame(train_data)
test_df = pd.DataFrame(test_data)


# add missing column from baseline if absent
if "requester_user_flair" not in train_df.columns:
    train_df["requester_user_flair"] = None
if "requester_user_flair" not in test_df.columns:
    test_df["requester_user_flair"] = None


train_df["target"] = train_df["requester_received_pizza"].astype(int)




# --------------------------------------------------------------
# 2. Text utilities
# --------------------------------------------------------------
def concat_text(df):
    return (
        df["request_title"].fillna("") + " " + df["request_text_edit_aware"].fillna("")
    ).values




train_texts = concat_text(train_df)
test_texts = concat_text(test_df)


# --------------------------------------------------------------
# 3. Sentence-Transformer embeddings -> PCA 64-D
# --------------------------------------------------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
MODEL = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2").to(DEVICE)
MODEL.eval()




def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]  # (bs, seq_len, hidden)
    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    summed = torch.sum(token_embeddings * mask, dim=1)
    divisor = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / divisor




def embed_batch(texts, batch_size=256):
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            enc = TOKENIZER(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            ids, mask = enc["input_ids"].to(DEVICE), enc["attention_mask"].to(DEVICE)
            out.append(mean_pooling(MODEL(ids, mask), mask).cpu().numpy())
    return np.vstack(out)




print("Embedding train texts …")
train_emb_full = embed_batch(train_texts)
print("Embedding test texts …")
test_emb_full = embed_batch(test_texts)


pca = PCA(n_components=64, random_state=SEED)
train_emb = pca.fit_transform(train_emb_full)
test_emb = pca.transform(test_emb_full)


# --------------------------------------------------------------
# 4. Basic numeric / cyclic time features + flair one‑hot
# --------------------------------------------------------------
NUMERIC_COLS = [
    "number_of_upvotes_of_request_at_retrieval",
    "number_of_downvotes_of_request_at_retrieval",
    "post_was_edited",
    "request_number_of_comments_at_retrieval",
    "requester_account_age_in_days_at_request",
    "requester_account_age_in_days_at_retrieval",
    "requester_days_since_first_post_on_raop_at_request",
    "requester_days_since_first_post_on_raop_at_retrieval",
    "requester_number_of_comments_at_request",
    "requester_number_of_comments_at_retrieval",
    "requester_number_of_comments_in_raop_at_request",
    "requester_number_of_comments_in_raop_at_retrieval",
    "requester_number_of_posts_at_request",
    "requester_number_of_posts_at_retrieval",
    "requester_number_of_posts_on_raop_at_request",
    "requester_number_of_posts_on_raop_at_retrieval",
    "requester_number_of_subreddits_at_request",
    "requester_upvotes_minus_downvotes_at_request",
    "requester_upvotes_minus_downvotes_at_retrieval",
    "requester_upvotes_plus_downvotes_at_request",
    "requester_upvotes_plus_downvotes_at_retrieval",
]


for df in (train_df, test_df):
    for col in NUMERIC_COLS:
        if col not in df:
            df[col] = 0
    hour = (df["unix_timestamp_of_request_utc"] % 86400) / 86400.0
    df["hour_sin"] = np.sin(2 * np.pi * hour)
    df["hour_cos"] = np.cos(2 * np.pi * hour)
    dow = ((df["unix_timestamp_of_request_utc"] // 86400) % 7) / 7.0
    df["dow_sin"] = np.sin(2 * np.pi * dow)
    df["dow_cos"] = np.cos(2 * np.pi * dow)


flair_map = {"shroom": 1, "PIF": 2}
for df in (train_df, test_df):
    df["flair_code"] = df["requester_user_flair"].map(flair_map).fillna(0).astype(int)


# Updated for newer sklearn versions
ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
flair_train = ohe.fit_transform(train_df[["flair_code"]])
flair_test = ohe.transform(test_df[["flair_code"]])




# --------------------------------------------------------------
# 5. Sub-reddit multi-hot (top 200)
# --------------------------------------------------------------
def top_n_subreddits(series, n=200):
    counter = Counter(itertools.chain.from_iterable(series))
    return [sub for sub, _ in counter.most_common(n)]




top_subs = top_n_subreddits(train_df["requester_subreddits_at_request"], n=200)


mlb = MultiLabelBinarizer(classes=top_subs)
sub_train = mlb.fit_transform(train_df["requester_subreddits_at_request"])
sub_test = mlb.transform(test_df["requester_subreddits_at_request"])


sub_train = np.asarray(sub_train, dtype=np.float32)
sub_test  = np.asarray(sub_test,  dtype=np.float32)


# --------------------------------------------------------------
# 6. Light textual features + sentiment
# --------------------------------------------------------------
sid = SentimentIntensityAnalyzer()




def text_stats(series):
    chars = series.str.len().fillna(0)
    words = series.str.split().apply(len).fillna(0)
    excls = series.str.count("!").fillna(0)
    ques = series.str.count(r"\?").fillna(0)
    sentiment = series.apply(lambda x: sid.polarity_scores(x or "")["compound"])
    return np.vstack([chars, words, excls, ques, sentiment]).T




txt_stats_train = text_stats(train_df["request_text_edit_aware"])
txt_stats_test = text_stats(test_df["request_text_edit_aware"])


# --------------------------------------------------------------
# 7. Assemble full feature matrices
# --------------------------------------------------------------
numeric_features = NUMERIC_COLS + ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]
X_num_train = train_df[numeric_features].values.astype(np.float32)
X_num_test = test_df[numeric_features].values.astype(np.float32)


scaler = StandardScaler()
X_num_train = scaler.fit_transform(X_num_train)
X_num_test = scaler.transform(X_num_test)


dense_train = np.hstack([train_emb, X_num_train, flair_train, txt_stats_train, sub_train])
dense_test = np.hstack([test_emb, X_num_test, flair_test, txt_stats_test, sub_test])


from scipy import sparse


X_train = sparse.hstack([sparse.csr_matrix(dense_train),
                         sparse.csr_matrix(sub_train)], format="csr")
X_test  = sparse.hstack([sparse.csr_matrix(dense_test),
                         sparse.csr_matrix(sub_test)],  format="csr")


y = train_df["target"].values.astype(np.float32)




# --------------------------------------------------------------
# 8. K-fold target encoding for username (for LightGBM)
# --------------------------------------------------------------
def target_encode(train_idx, val_idx, y, usernames, min_samples_leaf=100, smoothing=10):
    tr_user = usernames[train_idx]
    val_user = usernames[val_idx]
    agg = pd.DataFrame({"user": tr_user, "target": y[train_idx]})
    stats = agg.groupby("user")["target"].agg(["mean", "count"])
    smoothing_val = 1 / (1 + np.exp(-(stats["count"] - min_samples_leaf) / smoothing))
    prior = y.mean()
    stats["enc"] = prior * (1 - smoothing_val) + stats["mean"] * smoothing_val
    mapping = stats["enc"]
    val_enc = np.array([mapping.get(u, prior) for u in val_user])
    full_enc = np.empty_like(y, dtype=np.float32)
    full_enc[train_idx] = np.array([mapping.get(u, prior) for u in tr_user])
    full_enc[val_idx] = val_enc
    return full_enc




usernames = train_df["requester_username"].fillna("UNKNOWN").values


# --------------------------------------------------------------
# 9. 5-fold CV - train LightGBM & CatBoost, blend predictions
# --------------------------------------------------------------
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
fold_aucs = []
oof_preds = np.zeros_like(y, dtype=np.float32)


N = len(y)
assert dense_train.shape[0] == N == X_train.shape[0] == len(usernames)
assert dense_test.shape[0]  == len(test_df)


for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y)):
    # ----- LightGBM -----
    assert tr_idx.max() < N and val_idx.max() < N


    te_enc = target_encode(tr_idx, val_idx, y, usernames)
    X_tr_lgb = X_train[tr_idx]
    X_val_lgb = X_train[val_idx]
    te_tr = sparse.csr_matrix(te_enc[tr_idx].reshape(-1, 1))
    te_val = sparse.csr_matrix(te_enc[val_idx].reshape(-1, 1))
    X_tr_lgb = sparse.hstack([X_tr_lgb, te_tr],  format="csr")
    X_val_lgb = sparse.hstack([X_val_lgb, te_val], format="csr")


    lgb_train = lgb.Dataset(X_tr_lgb, label=y[tr_idx])
    lgb_val = lgb.Dataset(X_val_lgb, label=y[val_idx], reference=lgb_train)


    lgb_params = {
        "objective": "binary",
        "metric": "auc",
        "learning_rate": 0.05,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbosity": -1,
        "seed": SEED,
        "num_threads": 12,
    }


    lgb_model = lgb.train(
        lgb_params,
        lgb_train,
        num_boost_round=2000,
        valid_sets=[lgb_val],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )
    lgb_val_pred = lgb_model.predict(X_val_lgb)


    # ----- CatBoost -----
    # Build DataFrames that include the raw username column
    df_tr = pd.DataFrame(dense_train[tr_idx])
    df_tr["username"] = usernames[tr_idx]
    df_val = pd.DataFrame(
        dense_train[val_idx]
    )  # NOTE: we need test-like shape for validation
    df_val["username"] = usernames[val_idx]


    cat_features = ["username"]
    cat_tr = Pool(data=df_tr, label=y[tr_idx], cat_features=cat_features)
    cat_val = Pool(data=df_val, label=y[val_idx], cat_features=cat_features)


    cat_model = CatBoostClassifier(
        iterations=3000,
        learning_rate=0.03,
        depth=6,
        loss_function="Logloss",
        eval_metric="AUC",
        early_stopping_rounds=100,
        verbose=False,
        random_seed=SEED,
        thread_count=12,
    )
    cat_model.fit(cat_tr, eval_set=cat_val, use_best_model=True)


    cat_val_pred = cat_model.predict_proba(cat_val)[:, 1]


    # ----- Blend -----
    blended_val = 0.5 * lgb_val_pred + 0.5 * cat_val_pred
    oof_preds[val_idx] = blended_val
    auc = roc_auc_score(y[val_idx], blended_val)
    fold_aucs.append(auc)
    print(f"Fold {fold+1} AUC (blend): {auc:.5f}")


print(f"\nMean 5-fold AUC (blend): {np.mean(fold_aucs):.5f}")


# --------------------------------------------------------------
# 10. Retrain on full data (with internal hold-out) and predict test
# --------------------------------------------------------------
val_frac = 0.1
val_size = int(len(y) * val_frac)
perm = np.random.RandomState(SEED).permutation(len(y))
val_idx = perm[:val_size]
train_idx = perm[val_size:]


# LightGBM full training
te_full = target_encode(train_idx, val_idx, y, usernames)
X_full_lgb = X_train[train_idx]
X_val_lgb = X_train[val_idx]
X_full_lgb = sparse.hstack([X_full_lgb, te_full[train_idx][:, None]])
X_val_lgb = sparse.hstack([X_val_lgb, te_full[val_idx][:, None]])


lgb_train = lgb.Dataset(X_full_lgb, label=y[train_idx])
lgb_val = lgb.Dataset(X_val_lgb, label=y[val_idx], reference=lgb_train)


lgb_model_full = lgb.train(
    lgb_params,
    lgb_train,
    num_boost_round=2000,
    valid_sets=[lgb_val],
    callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
)


def target_encode_apply(train_usernames, y, query_usernames,
                        min_samples_leaf=100, smoothing=10):
    agg = pd.DataFrame({"user": train_usernames, "target": y})
    stats = agg.groupby("user")["target"].agg(["mean", "count"])
    s = 1 / (1 + np.exp(-(stats["count"] - min_samples_leaf) / smoothing))
    prior = float(y.mean())
    enc = prior * (1 - s) + stats["mean"] * s
    mapping = enc.to_dict()
    return np.array([mapping.get(u, prior) for u in query_usernames], dtype=np.float32)


test_usernames = test_df["requester_username"].fillna("UNKNOWN").values


te_test = target_encode_apply(usernames, y, test_usernames)          # shape (len(test),)
X_test_lgb = sparse.hstack(
    [X_test, sparse.csr_matrix(te_test.reshape(-1, 1))], format="csr"
)


test_pred_lgb = lgb_model_full.predict(X_test_lgb, num_iteration=lgb_model_full.best_iteration)


# CatBoost full training
df_full = pd.DataFrame(dense_train[train_idx])
df_full["username"] = usernames[train_idx]
df_val_full = pd.DataFrame(dense_train[val_idx])
df_val_full["username"] = usernames[val_idx]


cat_tr_full = Pool(data=df_full, label=y[train_idx], cat_features=["username"])
cat_val_full = Pool(data=df_val_full, label=y[val_idx], cat_features=["username"])


cat_model_full = CatBoostClassifier(
    iterations=3000,
    learning_rate=0.03,
    depth=6,
    loss_function="Logloss",
    eval_metric="AUC",
    early_stopping_rounds=100,
    verbose=False,
    random_seed=SEED,
    thread_count=12,
)
cat_model_full.fit(cat_tr_full, eval_set=cat_val_full, use_best_model=True)


test_usernames = test_df["requester_username"].fillna("UNKNOWN").values
df_test = pd.DataFrame(dense_test)
df_test["username"] = test_usernames


test_pred_cat = cat_model_full.predict_proba(Pool(df_test, cat_features=["username"]))[:, 1]


# Blend test predictions
test_pred = 0.5 * test_pred_lgb + 0.5 * test_pred_cat


# --------------------------------------------------------------
# 11. Save submission
# --------------------------------------------------------------
submission = pd.DataFrame(
    {"request_id": test_df["request_id"], "requester_received_pizza": test_pred}
)
submission_path = "./submission.csv"
submission.to_csv(submission_path, index=False)
print(f"\nSubmission saved to {submission_path}")