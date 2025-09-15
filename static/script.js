document.addEventListener('DOMContentLoaded', function () {
    // =================================================================
    // TODO: أدخل إعدادات Firebase الخاصة بك هنا
    // اذهب إلى Project Settings > General في Firebase Console
    // وابحث عن "Firebase SDK snippet" واختر "Config"
    // =================================================================
    const firebaseConfig = {
        apiKey: "YOUR_API_KEY",
        authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
        projectId: "YOUR_PROJECT_ID",
        storageBucket: "YOUR_PROJECT_ID.appspot.com",
        messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
        appId: "YOUR_APP_ID"
    };

    // Initialize Firebase
    firebase.initializeApp(firebaseConfig);
    const auth = firebase.auth();

    // عناصر الواجهة
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const userInfo = document.getElementById('user-info');
    const userEmail = document.getElementById('user-email');
    const mainContent = document.getElementById('main-content');
    const loginPrompt = document.getElementById('login-prompt');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');

    const separatorForm = document.getElementById('separator-form');
    const enhancerForm = document.getElementById('enhancer-form');

    let currentUser = null;
    let idToken = null;

    // مراقبة حالة تسجيل الدخول
    auth.onAuthStateChanged(async (user) => {
        if (user) {
            currentUser = user;
            idToken = await user.getIdToken();
            
            // تحديث الواجهة
            userEmail.textContent = user.email;
            userInfo.classList.remove('hidden');
            loginBtn.classList.add('hidden');
            mainContent.style.display = 'flex';
            loginPrompt.style.display = 'none';
        } else {
            currentUser = null;
            idToken = null;

            // تحديث الواجهة
            userInfo.classList.add('hidden');
            loginBtn.classList.remove('hidden');
            mainContent.style.display = 'none';
            loginPrompt.style.display = 'block';
        }
    });

    // تسجيل الدخول
    loginBtn.addEventListener('click', () => {
        const provider = new firebase.auth.GoogleAuthProvider();
        auth.signInWithPopup(provider).catch(error => {
            console.error("Login failed:", error);
            alert("فشل تسجيل الدخول.");
        });
    });

    // تسجيل الخروج
    logoutBtn.addEventListener('click', () => {
        auth.signOut();
    });

    // تحديث اسم الملف عند اختياره
    updateFileName('separator-file', 'separator-file-name');
    updateFileName('enhancer-file', 'enhancer-file-name');

    // التعامل مع رفع نموذج الفصل
    separatorForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('separator-file');
        if (fileInput.files.length === 0) {
            alert('الرجاء اختيار ملف أولاً.');
            return;
        }

        const formData = new FormData();
        formData.append('audio_file', fileInput.files[0]);
        formData.append('operation', 'separate');
        
        // إضافة الـ stems المختارة
        const checkedStems = separatorForm.querySelectorAll('input[name="stems"]:checked');
        if (checkedStems.length === 0) {
            alert("الرجاء اختيار مسار واحد على الأقل لفصله.");
            return;
        }
        checkedStems.forEach(stem => {
            formData.append('stems', stem.value);
        });

        startProcess(formData, 'separator-results');
    });

    // التعامل مع رفع نموذج التحسين
    enhancerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('enhancer-file');
        if (fileInput.files.length === 0) {
            alert('الرجاء اختيار ملف أولاً.');
            return;
        }

        const formData = new FormData();
        formData.append('audio_file', fileInput.files[0]);
        formData.append('operation', 'enhance');
        startProcess(formData, 'enhancer-results');
    });

    // بدء عملية المعالجة ومتابعتها
    async function startProcess(formData, resultsId) {
        showLoader(true, "جاري رفع الملف وبدء المعالجة...");
        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': `Bearer ${idToken}`
                }
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'حدث خطأ أثناء بدء المعالجة.');
            }
            
            const taskId = result.task_id;
            showLoader(true, `بدأت المعالجة (ID: ${taskId}). سيتم تحديث الحالة تلقائياً.`);
            pollTaskStatus(taskId, resultsId);

        } catch (error) {
            alert(error.message);
            showLoader(false);
        }
    }

    // متابعة حالة المهمة
    function pollTaskStatus(taskId, resultsId) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/task_status/${taskId}`, {
                    headers: { 'Authorization': `Bearer ${idToken}` }
                });
                const data = await response.json();

                if (data.status === 'completed') {
                    clearInterval(interval);

                    showLoader(false);
                    displayResults(resultsId, data.results);
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    showLoader(false);
                    alert(`فشلت المهمة: ${data.error}`);
                }
                // إذا كانت الحالة 'processing'، لا تفعل شيئًا واستمر في المتابعة
            } catch (error) {
                clearInterval(interval);
                showLoader(false);
                alert("فشل الاتصال بالخادم لمتابعة ا
