import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.metrics import mean_squared_error
from joblib import dump
from joblib import load

# Load the saved model from the file
model = load('model.joblib')
scaler = load('scaler.joblib')

new_data = [[20, 100]]
new_data_scaled = scaler.transform(new_data)

# Now, this loaded model can be used for making predictions
prediction = model.predict(new_data_scaled)

print(prediction)
