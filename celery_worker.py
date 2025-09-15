import os
import subprocess
import logging
from celery import Celery
from google.cloud import storage
import firebase_admin
from firebase_admin import credentials, firestore
import noisereduce as nr
from scipy.io import wavfile
import tempfile

# --- الإعدادات الأساسية ---
logging.basicConfig(level=logging.INFO)

# --- إعداد Celery ---
# استبدل REDIS_IP بعنوان IP الذي حصلت عليه من الخطوة 1
REDIS_URL = f"redis://{os.environ.get('REDIS_IP', 'localhost')}:6379/0"
celery_app = Celery('tasks', broker=REDIS_URL, backend=REDIS_URL)

# --- إعداد Firebase و GCS ---
if not firebase_admin._apps:
    # Note: In a real app, get credentials securely (e.g., from Secret Manager)
    cred = credentials.ApplicationDefault() 
    firebase_admin.initialize_app(cred)

db = firestore.client()
storage_client = storage.Client()
BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME') # Set this as an environment variable

@celery_app.task(bind=True)
def process_audio_task(self, task_data):
    task_id = self.request.id
    user_id = task_data['user_id']
    gcs_input_path = task_data['gcs_input_path']
    operation = task_data['operation']
    options = task_data.get('options', {})

    db.collection('tasks').document(task_id).set({
        'userId': user_id,
        'status': 'processing',
        'operation': operation,
        'createdAt': firestore.SERVER_TIMESTAMP
    })

    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        input_blob = bucket.blob(gcs_input_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            base_filename = os.path.basename(gcs_input_path)
            local_input_path = os.path.join(temp_dir, base_filename)
            input_blob.download_to_filename(local_input_path)
            
            output_files = {}

            if operation == 'separate':
                # دعم أكثر من stem
                stems = options.get('stems', ['vocals']) # Default to vocals
                model_name = "htdemucs"
                
                command = ["python3", "-m", "demucs.separate", "-n", model_name, "-o", temp_dir]
                if len(stems) == 1 and 'vocals' in stems:
                     command.extend(["--two-stems=vocals"])
                # Demucs default behavior separates all stems if --two-stems is not specified
                
                command.append(local_input_path)
                
                subprocess.run(command, check=True, capture_output=True, text=True)

                output_folder = os.path.join(temp_dir, model_name, os.path.splitext(base_filename)[0])
                
                # رفع الملفات الناتجة
                for stem_file in os.listdir(output_folder):
                    local_path = os.path.join(output_folder, stem_file)
                    gcs_path = f"processed/{user_id}/{task_id}/{stem_file}"
                    blob = bucket.blob(gcs_path)
                    blob.upload_from_filename(local_path)
                    output_files[os.path.splitext(stem_file)[0]] = blob.public_url

            elif operation == 'enhance':
                # نفس منطق التحسين السابق ولكن مع GCS
                wav_filepath = os.path.join(temp_dir, 'temp_for_enhance.wav')
                subprocess.run(['ffmpeg', '-i', local_input_path, wav_filepath, '-y'], check=True)
                rate, data = wavfile.read(wav_filepath)
                reduced_noise_data = nr.reduce_noise(y=data, sr=rate)
                
                output_filename = f"enhanced_{base_filename}.wav"
                local_output_path = os.path.join(temp_dir, output_filename)
                wavfile.write(local_output_path, rate, reduced_noise_data)

                gcs_path = f"processed/{user_id}/{task_id}/{output_filename}"
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_output_path)
                output_files['enhanced'] = blob.public_url

            # تحديث Firestore بالنتائج
            db.collection('tasks').document(task_id).update({
                'status': 'completed',
                'results': output_files,
                'completedAt': firestore.SERVER_TIMESTAMP
            })
            return {'status': 'completed', 'results': output_files}

    except Exception as e:
        logging.error(f"Task {task_id} failed: {e}")
        db.collection('tasks').document(task_id).update({'status': 'failed', 'error': str(e)})
        raise
