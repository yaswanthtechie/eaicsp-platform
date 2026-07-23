from sklearn.ensemble import IsolationForest

class IsolationForestModel:
    def __init__(self):
        self.model = IsolationForest(contamination = 0.004, random_state = 42)

    def train(self, features):
        self.model.fit(features)

    def predict(self, features):
        return self.model.predict(features)
    
    def score(self, features):
        return self.model.decision_function(features)
