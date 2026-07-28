from sklearn.neighbors import LocalOutlierFactor

class LOFModel:
    def __init__(self):
        self.model = LocalOutlierFactor(n_neighbors=20, contamination=0.004, novelty=True)

    def train(self, features):
        self.model.fit(features)

    def predict(self, features):
        return self.model.predict(features)
    
    def score(self, features):
        return self.model.decision_function(features)
