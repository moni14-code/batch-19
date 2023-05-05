from flask import Flask, render_template, request , send_file , Response,url_for,session,make_response
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_selection import SelectKBest, f_classif
from werkzeug.utils import secure_filename
import os
import io
import statsmodels.api as sm
import plotly.graph_objs as go
from datetime import datetime
from dash_application import create_dash_application
from datetime import timedelta
from sqlalchemy import create_engine

app=Flask(__name__)
app.config['STATIC_URL_PATH'] = '/static'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'csv'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize database engine for temporary data storage
db_engine = create_engine('sqlite:///temp.db')
processed_data=None


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/form')
def form():
    return render_template('form.html')

@app.route('/', methods=['POST'])
def preprocess():
    # Get uploaded file
    global processed_data
    file = request.files['file']
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    # Load dataset into a pandas dataframe
    df = pd.read_csv(file_path, sep=',')
    
    df.reset_index(inplace=True, drop=True)
    
    df['Order Date'] = pd.to_datetime(df['Order Date'])#changing the date to datetime format
    df['Ship Date'] = pd.to_datetime(df['Ship Date'])
    df['Shipping_timeframe'] = df['Ship Date'] -df['Order Date']
    df['Shipping_timeframe'].astype('str').str.split(expand=True)
    df[['Shipping_timeframe', '_']] = df['Shipping_timeframe'].astype('str').str.split(expand=True)
    df['Shipping_timeframe'] =df['Shipping_timeframe'].astype(int) 
    data_big = df[df['Shipping_timeframe'] >= 0] 
    data_big.groupby('Ship Mode').agg({'Shipping_timeframe':'mean'})
    ship_mode_dic = {"Standard Class":6,
                 "Second Class":4, 
                 "Same Day":0, 
                 "First Class":3}
    for key, value in ship_mode_dic.items():
        df['Ship Date'] = np.where((df['Shipping_timeframe'] < 0) & (df['Ship Mode'] == key),
                             df['Order Date'] + timedelta(days=value),
                             df['Ship Date'])
    df['Shipping_timeframe'] = df['Ship Date'] - df['Order Date']
    df['Shipping_timeframe'] = df['Ship Date'] - df['Order Date']
    df[['Shipping_timeframe', "not_important"]] =df['Shipping_timeframe'].astype('str').str.split(expand=True)
    df['Shipping_timeframe'] = df['Shipping_timeframe'].astype(int)
    df.drop(['Row ID', 'Country','not_important'], 1, inplace=True ) 
    df['Postal Code'] = df['Postal Code'].fillna('05402')
    upper=df.Sales.mean()+3*df.Sales.std()
    lower=df.Sales.mean()-3*df.Sales.std()
    df=df[(df.Sales<upper) & (df.Sales>lower)]
    processed_data = df.to_csv(index=False)
    return render_template('download.html', processed_data=processed_data)


@app.route('/download', methods=['POST'])
def download():
    # Get the processed data from the form data
    processed_data = request.form['processed_data']

    # Write the processed data to a file
    with open('processed_data.csv', 'w' ) as f:
        f.write(processed_data)

    # Set the response headers to trigger a download of the CSV file
    return send_file('processed_data.csv', as_attachment=True)

create_dash_application(app,processed_data_path='processed_data (4).csv')

sales_df = pd.read_csv('processed_data (4).csv')

# Converting the 'Date' column to datetime format
sales_df['Order Date'] = pd.to_datetime(sales_df['Order Date'])

# Aggregating the sales data by month
sales_monthly = sales_df.groupby(pd.Grouper(key='Order Date', freq='MS')).sum().reset_index()

# Renaming the columns as expected by ARIMA
sales_monthly = sales_monthly.rename(columns={"Order Date": "ds", "Sales": "y"})

# Creating an ARIMA model and fitting the sales data
arima_model = sm.tsa.arima.ARIMA(sales_monthly['y'], order=(1, 1, 1))
arima_model_fit = arima_model.fit()

# Forecasting the sales for the next 12 months
forecast = arima_model_fit.forecast(365)

# Creating the actual vs predicted sales plot using Plotly
plot_data = [go.Scatter(x=sales_monthly['ds'], y=sales_monthly['y'], name='Actual'),
             go.Scatter(x=pd.date_range(start=sales_monthly['ds'].max(), periods=365, freq='D'), y=forecast, name='Predicted')]

plot_layout = go.Layout(title='Actual vs Predicted Sales', xaxis_title='Date', yaxis_title='Sales')

plot_figure = go.Figure(data=plot_data, layout=plot_layout)

# Defining a route to display the sales forecast
@app.route('/sales_forecast')
def sales_forecast():
    download_link = '<a href="/download_sales_forecast" download>Download Sales Forecast</a>'
    
    return plot_figure.to_html(full_html=False)+ '<br><br>' + download_link

# Defining a route to download the sales forecast as a CSV file
@app.route('/download_sales_forecast')
def download_sales_forecast():
    # Creating a dataframe to hold the forecast data
    forecast_df = pd.DataFrame({'Predicted Sales': forecast})
    forecast_df.index = pd.date_range(start=sales_monthly['ds'].max(), periods=12, freq='MS')
    
    # Concatenating the actual sales and forecasted sales data into a single dataframe
    forecast_df = pd.concat([sales_monthly.set_index('ds')['y'], forecast_df], axis=1)
    forecast_df.columns = ['Actual Sales', 'Predicted Sales']
    
    # Creating a CSV file buffer to hold the forecast data
    csv_buffer = io.StringIO()
    forecast_df.to_csv(csv_buffer)
    csv_buffer.seek(0)
    
    response = make_response(csv_buffer)

    # set the headers to force a download
    response.headers.set('Content-Disposition', 'attachment', filename='sales_forecast.csv')
    response.headers.set('Content-Type', 'text/csv')
    # Returning the CSV file as a downloadable file
    return response



if __name__ == '__main__':
    app.run(debug=True)
