from sklearn.svm import OneClassSVM

class OneClassSVMModel:
    def __init__(self):
        self.model = OneClassSVM(nu=0.004, kernel='rbf', gamma='scale')

    def train(self, features):
        self.model.fit(features)

    def predict(self, features):
        return self.model.predict(features)
    
    def score(self, features):
        return self.model.decision_function(features)
