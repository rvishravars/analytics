---
title: "30-Day Kaggle + AI Engineer Roadmap"
author: "Vishravars"
date: ""
geometry: margin=1in
header-includes:
  - \usepackage{tabularx,longtable,booktabs}
  - \newcolumntype{Y}{>{\raggedright\arraybackslash}X}
---

## Phase 1 – ML Foundations (Days 1–10)

| Day | Kaggle Focus                    | Dataset Link                                                | AI Engineer Skill                                   | Progress |
|-----|---------------------------------|-------------------------------------------------------------|-----------------------------------------------------|----------|
|  1  | Titanic – Binary Classification | [Kaggle](https://www.kaggle.com/c/titanic)                | Environment setup; Git repo; reproducibility        | [*]      |
|  2  | House Prices – Regression       | [Kaggle](https://www.kaggle.com/c/house-prices-advanced-regression-techniques) | Data cleaning pipelines (pandas, sklearn.Pipeline)  | [*]      |
|  3  | Iris / Penguins – Multiclass    | [Kaggle](https://www.kaggle.com/uciml/iris)               | Notebook VC (nbdime, branches)                      | [ ]      |
|  4  | Heart Disease UCI               | [Kaggle](https://www.kaggle.com/ronitf/heart-disease-uci) | Feature eng + custom transformers                   | [ ]      |
|  5  | Customer Churn (IBM)            | [Kaggle](https://www.kaggle.com/blastchar/telco-customer-churn) | Imbalanced data (SMOTE, class weights, AUC)         | [ ]      |
|  6  | Wine Quality                    | [Kaggle](https://www.kaggle.com/uciml/red-wine-quality-cortez-et-al-2009) | Hyperparameter tuning with Optuna                   | [ ]      |
|  7  | Credit Card Fraud               | [Kaggle](https://www.kaggle.com/mlg-ulb/creditcardfraud)  | MLflow experiment tracking                           | [ ]      |
|  8  | Digit Recognizer (MNIST)        | [Kaggle](https://www.kaggle.com/c/digit-recognizer)       | PyTorch intro; GPU setup                            | [ ]      |
|  9  | SMS Spam Detection              | [Kaggle](https://www.kaggle.com/uciml/sms-spam-collection-dataset) | TF-IDF pipeline + evaluation                         | [ ]      |
| 10  | Tabular Playground              | [Kaggle](https://www.kaggle.com/competitions/tabular-playground-series-apr-2021) | Ensembles (boosting/stacking)                       | [ ]      |

## Phase 2 – ML Systems & Automation (Days 11–20)

| Day | Kaggle Focus                      | Dataset Link                                                                           | AI Engineer Skill                               | Progress |
|-----|-----------------------------------|----------------------------------------------------------------------------------------|-------------------------------------------------|----------|
| 11  | Santander Customer Transactions   | [Kaggle](https://www.kaggle.com/c/santander-customer-transaction-prediction)        | Data versioning with DVC                        | [ ]      |
| 12  | Fashion-MNIST                     | [Kaggle](https://www.kaggle.com/zalando-research/fashionmnist)                      | Dockerize training/inference                    | [ ]      |
| 13  | IMDB Reviews                      | [Kaggle](https://www.kaggle.com/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews)  | CLI inference script                            | [ ]      |
| 14  | Store Sales Forecasting           | [Kaggle](https://www.kaggle.com/competitions/store-sales-time-series-forecasting)   | Rolling-window features                         | [ ]      |
| 15  | Carvana Image Segmentation        | [Kaggle](https://www.kaggle.com/c/carvana-image-masking-challenge)                  | Config-driven training (YAML)                   | [ ]      |
| 16  | Toxic Comments                    | [Kaggle](https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge)    | Automated training (Makefile/bash)              | [ ]      |
| 17  | House Rent Prediction             | [Kaggle](https://www.kaggle.com/datasets/ghousethedev/house-rent-prediction)       | Deploy REST API (FastAPI)                       | [ ]      |
| 18  | Traffic Flow Prediction           | [Kaggle](https://www.kaggle.com/datasets/yasserh/traffic-volume-prediction)        | Dockerized FastAPI inference                     | [ ]      |
| 19  | Zoo Dataset                       | [Kaggle](https://www.kaggle.com/uciml/zoo-animal-classification)                   | Unit tests with pytest                          | [ ]      |
| 20  | Any previous model                | —                                                                                      | CI/CD (GitHub Actions)                          | [ ]      |

## Phase 3 – Applied AI Engineering (Days 21–30)

| Day | Kaggle Focus             | Dataset Link                                                                                   | AI Engineer Skill                             | Progress |
|-----|--------------------------|--------------------------------------------------------------------------------------------------|-----------------------------------------------|----------|
| 21  | Text Summarization       | [Kaggle](https://www.kaggle.com/datasets/taranjeet/text-summarization)                        | HF transformers inference                     | [ ]      |
| 22  | Sentiment Analysis       | [Kaggle](https://www.kaggle.com/datasets/kazanova/sentiment140)                               | Fine-tune transformer                         | [ ]      |
| 23  | Product Images           | [Kaggle](https://www.kaggle.com/datasets/muhammadkhalid/sign-language-mnist)                  | Convert to ONNX/TorchScript                   | [ ]      |
| 24  | Speech Commands          | [Kaggle](https://www.kaggle.com/competitions/tensorflow-speech-recognition-challenge)         | Audio preprocessing pipeline                   | [ ]      |
| 25  | OpenAI/HF API            | [Hugging Face Datasets](https://huggingface.co/datasets)                                      | Prompt engineering + evaluation               | [ ]      |
| 26  | Dataset of Choice        | —                                                                                                | Streamlit demo UI                             | [ ]      |
| 27  | Multi-Modal (text+image) | [CLIP example](https://www.kaggle.com/code/kaustubhdikshit/clip-contrastive-language-image-pre-training) | Combine embeddings (CLIP/BLIP)                | [ ]      |
| 28  | Self-Curated Dataset     | —                                                                                                | Automated retraining pipeline                 | [ ]      |
| 29  | Best Model from Portfolio| —                                                                                                | Cloud deploy (Render/EC2)                     | [ ]      |
| 30  | —                        | —                                                                                                | Portfolio README + LinkedIn post              | [ ]      |

## Milestones
- [ ] 5 models containerized
- [ ] 1 FastAPI or Streamlit app online
- [ ] 1 CI/CD pipeline functional
- [ ] All datasets versioned/tracked
- [ ] Portfolio published (GitHub + LinkedIn)

## Daily Reflection (template)

> - What did I learn today?
> - What went wrong?
> - What will I automate next?
> - Next AI Engineer milestone to reach.
