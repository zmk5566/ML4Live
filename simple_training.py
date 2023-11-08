import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.metrics import mean_squared_error
from joblib import dump

# Load the dataset
dataframe = pd.read_csv('./training_dataset/data.csv')

# Separate features and target
X = dataframe[['sensor_a', 'sensor_b']]
y = dataframe['prediction']

# Split into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Scale features (important for SVMs)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train SVR model
model = SVR(kernel='rbf', C=100, gamma=0.1, epsilon=.1)
model.fit(X_train_scaled, y_train)


# Make predictions
y_pred = model.predict([[20, 20]])

# Compute MSE
#mse = mean_squared_error(y_test, y_pred)

print(y_pred)


# Save the trained model as a file
dump(model, 'model.joblib')
dump(scaler, 'scaler.joblib')

#print(f"Mean Squared Error: {mse:.2f}")
