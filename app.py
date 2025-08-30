import os
import subprocess
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import noisereduce as nr
from scipy.io import wavfile
import torch

# --- الإعدادات الأساسية ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# --- إعدادات المجلدات ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'processed')
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/separate', methods=['POST'])
def separate_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "لم يتم إرسال أي ملف"}), 400
    
    file = request.files['audio_file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "ملف غير صالح أو لم يتم اختياره"}), 400

    try:
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        logging.info(f"الملف '{filename}' تم حفظه بنجاح.")

        # --- استخدام Demucs لفصل الصوت ---
        # سيقوم Demucs بإنشاء مجلد داخل PROCESSED_FOLDER
        model_name = "htdemucs" # اسم النموذج المستخدم
        output_dir = app.config['PROCESSED_FOLDER']
        
        logging.info(f"بدء عملية الفصل باستخدام Demucs للملف: {input_path}")
        # نستخدم subprocess لتشغيل Demucs لتجنب مشاكل الذاكرة
        command = [
            "python3", "-m", "demucs.separate",
            "-n", model_name,
            "-o", str(output_dir),
            "--two-stems=vocals", # لإنتاج مسار للمغني ومسار للموسيقى
            str(input_path)
        ]
        
        # تحديد الجهاز (CPU) لأن Cloud Run لا يحتوي على GPU
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = ""

        process = subprocess.run(command, capture_output=True, text=True, env=env)

        if process.returncode != 0:
            logging.error(f"فشل Demucs: {process.stderr}")
            raise Exception("فشلت عملية معالجة الصوت.")
        
        logging.info("اكتملت عملية الفصل بنجاح.")

        base_filename = os.path.splitext(filename)[0]
        # المسار الذي ينشئه Demucs
        result_folder = os.path.join(output_dir, model_name, base_filename)
        
        vocals_path = os.path.join(result_folder, 'vocals.wav')
        accompaniment_path = os.path.join(result_folder, 'no_vocals.wav') # Demucs يسميه no_vocals

        if not os.path.exists(vocals_path) or not os.path.exists(accompaniment_path):
            raise Exception("لم يتم العثور على الملفات الناتجة.")
        
        return jsonify({
            "files": {
                "vocals": f"/processed/{model_name}/{base_filename}/vocals.wav",
                "accompaniment": f"/processed/{model_name}/{base_filename}/no_vocals.wav"
            }
        })

    except Exception as e:
        logging.error(f"حدث خطأ فادح: {e}")
        return jsonify({"error": f"حدث خطأ أثناء المعالجة: {str(e)}"}), 500


@app.route('/enhance', methods=['POST'])
def enhance_audio():
    if 'audio_file' not in request.files:
        return jsonify({"error": "لم يتم إرسال أي ملف"}), 400
    
    file = request.files['audio_file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "ملف غير صالح أو لم يتم اختياره"}), 400

    try:
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        logging.info(f"الملف '{filename}' تم حفظه بنجاح للتحسين.")
        
        # تحويل الملف إلى صيغة WAV للمعالجة
        wav_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_for_enhance.wav')
        subprocess.run(['ffmpeg', '-i', input_path, wav_filepath, '-y'], check=True)
        
        rate, data = wavfile.read(wav_filepath)
        
        # إزالة الضوضاء
        logging.info("بدء عملية إزالة الضوضاء...")
        reduced_noise_data = nr.reduce_noise(y=data, sr=rate, stationary=True)
        logging.info("اكتملت إزالة الضوضاء.")
        
        output_filename = f"enhanced_{os.path.splitext(filename)[0]}.wav"
        output_filepath = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        wavfile.write(output_filepath, rate, reduced_noise_data)
        
  
