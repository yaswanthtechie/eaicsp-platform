from sklearn.metrics import accuracy_score
from sklearn.metrics import f1_score


def evaluate(model, X_test, y_test):

    prediction = model.predict(X_test)

    accuracy = accuracy_score(y_test, prediction)

    f1 = f1_score(y_test, prediction, average="weighted")

    return accuracy, f1