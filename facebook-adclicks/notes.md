# Presentation Notes: Predicting Clicks on Ads

---

## Online Data Joiner - Data Flow
* This slide shows the model's real-time learning setup.
* The **Ranker** shows ads to the user.
* Features `{x}` and clicks `{y}` are sent to the **Online Joiner**.
* The Joiner creates labeled training data `{x, y}` for the **Trainer**.
* The Trainer updates the models and sends them back to the Ranker.

---

## Online Data Joiner (Method)
* The system trains an online Logistic Regression model with Stochastic Gradient Descent (SGD).
* It uses a **per-coordinate learning rate**.
* Per co-ordinate SGD uses weights over mean/variance &&& model size is half.

---

## Online Data Joiner - Challenges & Solution
* How to efficiently join impressions and clicks? Massive
* **HashQueue** system uses a FIFO queue to buffer recent impressions and a hash map for instant lookup when a click event arrives.
* **Anomaly detection** is used to disconnect the trainer from the joiner if corrupted data is detected - protecting the live models.

---

## Memory & Latency - Boosted Tree (Setup)
* Find the optimal number of decision trees to balance prediction speed and accuracy.

* Train the model on one full day of data.
* Vary the number of trees in the model from 1 to 2,000.
* Test the performance on the next consecutive day.
* Restrict each tree to a maximum of 12 leaves.

---

## Memory & Latency - Boosted Tree (Results)
* Adding more trees improves accuracy, but with **diminishing returns**.
* Most of the accuracy gain comes from the **first 500 trees**. Adding more provides less than a 0.1% improvement.
* Too many trees can cause **overfitting**, where the model performs worse, especially on smaller datasets.

---

## Memory & Latency - Feature Importance (Setup)
* Not all features are created equal; some are more important than others for prediction.
* They use **"Boosting Feature Importance"** to rank features.
* This score is the sum of the error reduction a feature provides every time it's used to split a node in a tree.

---

## Memory & Latency - Feature Importance (Results)
* A very small subset of features provides most of the model's predictive power.
* The **top 10 features** account for about **50% of the total importance**.
* This allows for aggressive feature selection, which improves speed and reduces memory usage without significantly hurting accuracy.

---
