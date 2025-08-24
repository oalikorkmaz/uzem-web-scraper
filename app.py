# app.py

from flask import Flask, render_template, request, jsonify, send_from_directory
import json
from tasks import start_scrape_process, celery_app
from celery.result import AsyncResult
import os

app = Flask(__name__)

# Ana sayfa. Kullanıcıya HTML arayüzünü gösterir.
@app.route('/', methods=['GET'])
def index():
    return render_template('uzem_scraper_interface.html')

# Veri çekme işlemini başlatan endpoint.
@app.route('/start-scrape', methods=['POST'])
def start_scrape():
    username = request.form['username']
    password = request.form['password']
    minimum_values = json.loads(request.form['minimum_values'])
    selected_languages = json.loads(request.form.get('selected_languages', '[]'))

    # Celery görevini başlat ve hemen bir görev ID'si al.
    task = start_scrape_process.delay(username, password, minimum_values, selected_languages)
    return jsonify({"task_id": task.id})

# Görevin durumunu sorgulayan endpoint.
@app.route('/task-status/<task_id>', methods=['GET'])
def task_status(task_id):
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        response = {'state': task.state, 'progress': 0, 'log_message': 'Görev kuyrukta bekliyor...'}
    elif task.state == 'PROGRESS':
        response = {'state': task.state, 'progress': task.info.get('progress', 0), 'log_message': task.info.get('log_message', '')}
    elif task.state == 'SUCCESS':
        response = {'state': task.state, 'result': task.get()}
    else: # FAILURE
        response = {'state': task.state, 'log_message': str(task.info)}
        
    return jsonify(response)

# Oluşturulan Excel dosyasını indirme endpoint'i.
@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    # Güvenlik için dosya yolunu temizle
    if '..' in filename or filename.startswith('/'):
        return "Geçersiz dosya adı", 400
    
    return send_from_directory(directory='output', path=filename, as_attachment=True)