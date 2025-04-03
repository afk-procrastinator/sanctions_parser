# Deployment Guide

This guide provides step-by-step instructions for deploying the Sanctions Update Scraper to various platforms.

## Table of Contents
- [Heroku](#heroku)
- [Railway](#railway)
- [PythonAnywhere](#pythonanywhere)
- [AWS Elastic Beanstalk](#aws-elastic-beanstalk)
- [Vercel](#vercel)

## Heroku

### Prerequisites
- A Heroku account (https://signup.heroku.com)
- Heroku CLI installed (https://devcenter.heroku.com/articles/heroku-cli)
- Git installed

### Steps

1. **Create a Procfile**

   Create a file named `Procfile` (no extension) in your project root with the following content:
   ```
   web: gunicorn app:app
   ```

2. **Add gunicorn to requirements.txt**

   Add the following line to your `requirements.txt`:
   ```
   gunicorn==20.1.0
   ```

3. **Login to Heroku**

   ```bash
   heroku login
   ```

4. **Create a new Heroku app**

   ```bash
   heroku create your-app-name
   ```

5. **Push to Heroku**

   ```bash
   git add .
   git commit -m "Prepare for Heroku deployment"
   git push heroku main
   ```

6. **Open your app**

   ```bash
   heroku open
   ```

## Railway

### Prerequisites
- A Railway account (https://railway.app)
- Railway CLI installed (optional)

### Steps

1. **Create a Procfile**

   Create a file named `Procfile` (no extension) in your project root with the following content:
   ```
   web: gunicorn app:app
   ```

2. **Add gunicorn to requirements.txt**

   Add the following line to your `requirements.txt`:
   ```
   gunicorn==20.1.0
   ```

3. **Deploy using the Railway dashboard**

   - Go to https://railway.app/dashboard
   - Click "New Project" and select "Deploy from GitHub repo"
   - Connect your GitHub account and select your repository
   - Railway will automatically detect your Python app
   - Click "Deploy Now"

4. **Configure your app**

   - In the Railway dashboard, navigate to your project
   - Under the "Settings" tab, add the following environment variables if needed:
     - `PORT`: 8080
   - Click "Generate Domain" to create a public URL for your app

## PythonAnywhere

### Prerequisites
- A PythonAnywhere account (https://www.pythonanywhere.com)

### Steps

1. **Create a new web app**

   - Log in to PythonAnywhere
   - Go to the Web tab and click "Add a new web app"
   - Choose "Flask" and the latest Python version

2. **Upload your code**

   - Go to the Files tab
   - Upload your project files or clone from GitHub:
     ```
     git clone https://github.com/yourusername/your-repo.git
     ```

3. **Set up a virtual environment**

   ```bash
   mkvirtualenv --python=/usr/bin/python3.9 myenv
   pip install -r requirements.txt
   ```

4. **Configure the WSGI file**

   Navigate to the WSGI configuration file and update it:
   ```python
   import sys
   path = '/home/yourusername/your-project-directory'
   if path not in sys.path:
       sys.path.append(path)
   
   from app import app as application
   ```

5. **Reload your web app**

   Go back to the Web tab and click the "Reload" button.

## AWS Elastic Beanstalk

### Prerequisites
- An AWS account
- AWS CLI installed
- EB CLI installed
- Git installed

### Steps

1. **Initialize your EB CLI repository**

   ```bash
   eb init -p python-3.9 sanctions-scraper
   ```

2. **Create a .ebignore file**

   Create a `.ebignore` file to exclude files you don't want to deploy:
   ```
   .git
   .gitignore
   .env
   __pycache__/
   *.pyc
   venv/
   ```

3. **Create an application.py file**

   Rename `app.py` to `application.py` or create a symlink:
   ```bash
   ln -s app.py application.py
   ```

4. **Create a requirements.txt file**

   Ensure your `requirements.txt` has all necessary dependencies:
   ```
   flask==2.3.3
   requests==2.31.0
   beautifulsoup4==4.12.2
   ```

5. **Deploy your application**

   ```bash
   eb create sanctions-scraper-env
   ```

6. **Open your application**

   ```bash
   eb open
   ```

## Vercel

### Prerequisites
- A Vercel account (https://vercel.com/signup)
- Vercel CLI installed (optional)

### Steps

1. **Create a vercel.json file**

   Create a file named `vercel.json` in your project root:
   ```json
   {
     "version": 2,
     "builds": [
       {
         "src": "app.py",
         "use": "@vercel/python"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "app.py"
       }
     ]
   }
   ```

2. **Deploy using the Vercel dashboard**

   - Go to https://vercel.com/dashboard
   - Click "New Project" and import your GitHub repository
   - Follow the setup instructions and deploy

3. **Deploy using the Vercel CLI (alternative)**

   ```bash
   npm i -g vercel
   vercel login
   vercel
   ```

## Additional Considerations

When deploying your application to a public server, consider the following:

1. **Security**:
   - Set up proper authentication if needed
   - Use HTTPS for all traffic
   - Set appropriate CORS headers

2. **Error handling**:
   - Add more robust error handling
   - Implement logging

3. **Scaling**:
   - Consider how your application will handle multiple concurrent users
   - Implement caching to reduce server load and improve responsiveness

4. **Monitoring**:
   - Set up monitoring and alerts
   - Implement health check endpoints 