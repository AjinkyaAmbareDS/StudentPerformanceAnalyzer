"""Simple scikit-learn risk classifier for the StudentIQ college-project prototype.

Important: this model is trained on generated illustrative examples, not real student data.
Replace the synthetic training data with ethically collected, consented, representative data
before using it for real decisions. Treat predictions as a support signal, never as a verdict.
"""
import os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

_MODEL = None
_LABELS = ["Low", "Medium", "High"]

def train_model():
    global _MODEL
    rng = np.random.default_rng(17)
    n = 1800
    average = rng.uniform(25, 100, n)
    attendance = rng.uniform(35, 100, n)
    assessments = rng.integers(1, 12, n)
    # Illustrative labels created from transparent thresholds plus small noise.
    score = (average < 50) | (attendance < 60)
    medium = (average < 65) | (attendance < 75)
    labels = np.where(score, "High", np.where(medium, "Medium", "Low"))
    # Add modest label noise to make this a classification exercise rather than exact rules.
    noise = rng.random(n) < 0.035
    for i in np.where(noise)[0]:
        labels[i] = rng.choice(_LABELS)
    X = np.column_stack([average, attendance, assessments])
    model = make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=140, max_depth=8, random_state=17, class_weight="balanced"))
    model.fit(X, labels)
    _MODEL = model
    return model

def predict_risk(average, attendance, assessments_count):
    global _MODEL
    if _MODEL is None:
        train_model()
    X = np.array([[float(average), float(attendance), max(1, int(assessments_count))]])
    pred = str(_MODEL.predict(X)[0])
    probs = _MODEL.predict_proba(X)[0]
    probability = round(float(max(probs))*100, 1)
    return {"risk":pred,"probability":probability,
            "model_note":"Experimental ML model trained on synthetic demo examples."}
