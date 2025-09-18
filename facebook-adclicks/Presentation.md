# INFO411 Online Data Joiner
## Practical Lessons from Predicting Clicks on Ads at Facebook

---

## Online Data Joiner – Data Flow

**Task**: Stream real-time training data

❓How to join *freshness* vs. *click impressions*❓

![Online Joiner Flow](images/OnlineJoinerFlow.png)

Similar infrastructure used by **google advertisements !**

<div style="text-align: center; margin-top: 0.5rem;">
<a href="#memory-trees" style="font-size: 2rem; text-decoration: none;">⬇️ Next</a>
</div>

---

## Online Data Joiner

**Per-coordinate learning rate**:

$$
\eta_{t,i} = \frac{\alpha}{\beta + \sqrt{\sum_{j=1}^t g_{j,i}^2}} 
$$

- Train **Online Logistic Regression** with **SGD**
- Marginally better than **BOPR**
- ❓Challenges in Online Data Joining❓

---

## Online Data Joiner - Challenges & Solution

**Anomaly detection** - Trainer <-x-> Joiner

**HashQueue** & **Request ID** for efficient stream-to-stream joining.

![alt text](images/generated-image.png)

---

## Memory & Latency – Boosted Trees

![Feature Importance vs Cumulative](images/BoostingSubmodelvsNE.png)

- Prediction accuracy improves with more boosted trees, mostly within the **first 500 trees**.

- Beyond 500 trees, gains diminish; overfitting occurs in submodel 2 after **1,000 trees**.

- **Overfitting** is due to smaller training data in **submodel 2** compared to others.

---

## Memory & Latency – Feature Importance

<div id="memory-features">

![Feature Importance vs Cumulative](images/ImportanceVsCummulativeImp.png)

**Findings**:
Top **10 features ≈ 50%** of total feature importance  
Small subset of features accounts for most predictive power  
**Question**: Which features are most critical

<div style="text-align: center; margin-top: 1rem;">
<a href="#historical-context" style="font-size: 2rem; text-decoration: none;">⬇️ Next</a>
</div>

</div>

---

## Historical vs. Contextual Features
<div id="historical-context">

![Feature Importance vs Cumulative](images/HistoricalvsContextual.png)

- **Findings**: **Historical >> Contextual** in accuracy   
- **Question**: How to best **combine history + context**?
Note: Contextual features essential for **cold start** scenarios

<div style="text-align: center; margin-top: 1rem;">
<a href="#massive-approach" style="font-size: 2rem; text-decoration: none;">⬇️ Next</a>
</div>

---