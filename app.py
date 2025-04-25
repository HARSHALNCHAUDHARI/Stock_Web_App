from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend suitable for web apps
import matplotlib.pyplot as plt
import yfinance as yf
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import os
import io
import secrets
import sqlite3
from flask import flash
import base64
from sklearn.metrics import mean_squared_error, mean_absolute_error


from flask import Flask, request, jsonify, session, redirect
from google.oauth2 import id_token
from google.auth.transport import requests

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  


GOOGLE_CLIENT_ID = "636335894415-uerbtsbvgk5bnliefp1epam5ektpnr7t.apps.googleusercontent.com"  

@app.route('/google-login', methods=['POST'])
def google_login():
    token = request.json.get('token')
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)

        # Token is valid; extract user info
        user_email = idinfo['email']
        user_name = idinfo.get('name', '')

        # Store in session or DB
        session['user'] = {'email': user_email, 'name': user_name}

        return jsonify({'status': 'success', 'email': user_email, 'name': user_name})

    except ValueError:
        # Invalid token
        return jsonify({'status': 'error'}), 400
    
    
    

#Load Model
model = tf.keras.models.load_model('/Users/seflame/Desktop/Stock_Web_App/main_trained_model.keras')



def plot_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return image_base64

@app.route('/')
def index():
    username = session.get('username')
    return render_template('index.html', username=username)

@app.route('/prediction', methods=['GET', 'POST'])
def prediction():
    if not session.get('logged_in'):
        return redirect(url_for('login', next=request.url))  
    return render_template('prediction.html', username=session.get('username'))

@app.route('/learning')
def learning():
    if not session.get('logged_in'):
        return redirect(url_for('login', next=request.url))
    return render_template('learning.html', username=session.get('username'))


@app.route('/mutualfunds')
def mutualfunds():
    return render_template('mutualfunds.html')


@app.route('/fetch-data', methods=['POST'])
def fetch_data():
    stock = request.form.get('ticker')
    start = request.form.get('start')
    end = request.form.get('end')

    try:
        # Convert to datetime to validate
        start_date = pd.to_datetime(start)
        end_date = pd.to_datetime(end)

        if start_date >= end_date:
            return jsonify({'error': 'Start date must be before end date.'})

        df = yf.download(stock, start=start, end=end)

        if df.empty:
            return jsonify({'error': 'Invalid stock ticker or no data found for given date range.'})

        # Summary Table
        summary_html = df.describe().to_html(classes="data-table", border=0)

        # === Plot 1: Open and Close Prices ===
        fig1 = plt.figure(figsize=(10, 5))
        plt.plot(df['Open'], label='Open Price', color='red')
        plt.plot(df['Close'], label='Close Price', color='orange')
        plt.title("Open vs Close Price")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        open_close_plot = plot_to_base64(fig1)

        # === Plot 2: MA100 vs MA200 ===
        df['MA100'] = df['Close'].rolling(100).mean()
        df['MA200'] = df['Close'].rolling(200).mean()
        fig2 = plt.figure(figsize=(10, 5))
        plt.plot(df['Close'], label='Close Price', color='gray')
        plt.plot(df['MA100'], label='MA100', color='green')
        plt.plot(df['MA200'], label='MA200', color='red')
        plt.title("100-day vs 200-day Moving Average")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        ma_plot = plot_to_base64(fig2)

        # === Prediction Plot ===
        data_training = df['Close'][:int(len(df)*0.70)]
        data_testing = df['Close'][int(len(df)*0.70):]

        scaler = MinMaxScaler(feature_range=(0, 1))
        data_training_array = scaler.fit_transform(np.array(data_training).reshape(-1, 1))

        past_100_days = data_training[-100:]
        final_df = pd.concat([past_100_days, data_testing], ignore_index=True)
        input_data = scaler.fit_transform(np.array(final_df).reshape(-1, 1))

        x_test, y_test = [], []
        for i in range(100, input_data.shape[0]):
            x_test.append(input_data[i-100:i])
            y_test.append(input_data[i, 0])

        x_test = np.array(x_test)
        y_test = np.array(y_test)
        y_predicted = model.predict(x_test)

        scale_factor = 1 / scaler.scale_[0]
        y_predicted = y_predicted * scale_factor
        y_test = y_test * scale_factor

        fig3 = plt.figure(figsize=(10, 5))
        plt.plot(y_test, label='Original Price', color='blue')
        plt.plot(y_predicted, label='Predicted Price', color='red')
        plt.title("Original vs Predicted Price")
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.legend()
        prediction_plot = plot_to_base64(fig3)
        
        


        return jsonify({
            'summary': summary_html,
            'open_close_plot': open_close_plot,
            'ma_plot': ma_plot,
            'prediction_plot': prediction_plot,
            })


    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials. Please try again.")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        mobile_number = request.form.get('mobile_number')
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (full_name, mobile_number, username, password) VALUES (?, ?, ?, ?)",
                      (full_name, mobile_number, username, password))
            conn.commit()
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists. Please try a different one.")
            return redirect(url_for('signup'))
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')



if __name__ == '__main__':
    app.run(debug=True , port=5002)
