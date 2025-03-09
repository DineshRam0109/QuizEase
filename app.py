import os
from flask import Flask, render_template, request, send_file,jsonify
import pdfplumber
import docx
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF  # pip install fpdf
from googletrans import Translator  # pip install googletrans==4.0.0-rc1
import speech_recognition as sr  # pip install SpeechRecognition
import pyttsx3  # pip install pyttsx3
from PyPDF2.errors import PdfReadError
from pdfminer.pdfparser import PDFSyntaxError
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()  # Loads environment variables from .env


app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# your existing routes...


# Set your API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "E:\\dinesh mcq generator\\upload folder"
app.config['RESULTS_FOLDER'] = "E:\\dinesh mcq generator\\result folder"
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    
    if ext == 'pdf':
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ''.join([page.extract_text() for page in pdf.pages if page.extract_text()])
            return text
        except PDFSyntaxError as e:
            print(f"Error while extracting text from PDF: {e}")
            return None
    elif ext == 'docx':
        try:
            doc = docx.Document(file_path)
            text = ' '.join([para.text for para in doc.paragraphs if para.text])
            return text
        except Exception as e:
            print(f"Error while reading DOCX: {e}")
            return None
    elif ext == 'txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            return text
        except Exception as e:
            print(f"Error while reading TXT file: {e}")
            return None
    else:
        return None

def Question_mcqs_generator(input_text, num_questions):
    i=1
    prompt = f"""
    You are an AI assistant helping the user generate multiple-choice questions (MCQs) based on the following text:
    '{input_text}'
    
    Please generate {num_questions} distinct and clear MCQs from the text. Each question should:
    - Be well-phrased, specific, and relevant to the content.
    - Include four answer options (labeled A, B, C, D).
    - Clearly indicate the correct answer among the options.
    - Provide a detailed explanation for why the correct answer is correct. The explanation should:
        - Be accurate and based on the context from the provided text.
        - Explain why the other options are incorrect, if applicable.
        - Be well-articulated, concise, and relevant to the question.

    Format each question as:
    Q{i}: [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [correct option]
    Explanation: [detailed explanation of the correct answer, including reasons for the other options being incorrect]

    Do not include any additional information, just the MCQ question, answer options, correct answer, and explanation.
    """
    i+=1
    response = model.generate_content(prompt).text.strip()
    return response

def translate_text(text, target_language):
    try:
        translator = Translator()
        translation = translator.translate(text, dest=target_language)
        return translation.text
    except Exception as e:
        print(f"Error during translation: {e}")
        return text  # Return the original text if translation fails

def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    with open(results_path, 'w', encoding='utf-8') as f:
        f.write(mcqs)
    return results_path

def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()     
    # Ensure the correct font path for DejaVu font (provide the absolute path to the font)
    try:
        pdf.add_font('DejaVu', '', "E:\\dinesh mcq generator\\dejavu-fonts-ttf-2.37\\ttf\\DejaVuSans.ttf")
    except Exception as e:
        print(f"Font loading error: {e}")
        pdf.set_font("Arial", size=12)  # Use default font if DejaVu fails
    
    pdf.set_font("DejaVu", size=12)

    for mcq in mcqs.split("\n\n"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)  # Add a line break

    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

def listen_for_voice_command():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for voice command...")
        audio = recognizer.listen(source)
        try:
            command = recognizer.recognize_google(audio)
            print(f"Command received: {command}")
            return command.lower()
        except sr.UnknownValueError:
            print("Could not understand the audio.")
            return None
        except sr.RequestError as e:
            print(f"Error with the speech recognition service: {e}")
            return None

def speak_response(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_mcqs():
    if 'file' not in request.files:
        return "No file part"

    file = request.files['file']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Extract text from the uploaded file
        text = extract_text_from_file(file_path)

        # Check if the extraction was successful or if the file is empty/invalid
        if not text:
            return "The uploaded file is empty or invalid. Please upload a valid extension with content."

        num_questions = int(request.form['num_questions'])
        mcqs = Question_mcqs_generator(text, num_questions)

        # Translate the MCQs if a language option is selected
        selected_language = request.form['language']
        if selected_language != 'english':
            mcqs = translate_text(mcqs, selected_language)

        # Save the generated MCQs to a file
        txt_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.txt"
        pdf_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.pdf"
        save_mcqs_to_file(mcqs, txt_filename)
        create_pdf(mcqs, pdf_filename)

        # Display and allow downloading
        return render_template('results.html', mcqs=mcqs, txt_filename=txt_filename, pdf_filename=pdf_filename)
    return "Invalid file format"

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

@app.route('/voice', methods=['POST'])
def voice_command():
    """
    Handles voice commands to dynamically update the form fields.
    """
    data = request.get_json()
    command = data.get("command", "").lower().strip()  # Capture and sanitize the command
    print(f"Command received: '{command}'")  # Debugging: Print the received command

    response = {"status": "success"}  # Default success response

    if "set language to" in command:  # Check if the command is for setting language
        language = command.split("set language to ")[-1].strip().capitalize()
        supported_languages = {
            "English": "english",
            "Hindi": "hi",
            "Tamil": "ta",
            "Gujarati": "gu",
            "Telugu": "te",
            "Malayalam": "ml",
            "French": "fr",
        }
        if language in supported_languages:  # Validate the language
            response["message"] = f"Language set to {language}."
            response["language"] = supported_languages[language]
        else:
            response["status"] = "error"
            response["message"] = f"Language '{language}' not supported."

    elif "set questions to" in command:  # Check if the command is for setting number of questions
        try:
            num_questions = int(command.split("set questions to ")[-1].strip())
            response["message"] = f"Number of questions set to {num_questions}."
            response["num_questions"] = num_questions
        except ValueError:  # Handle invalid number input
            response["status"] = "error"
            response["message"] = "Invalid number for questions."

    else:
        response["status"] = "error"
        response["message"] = "Command not recognized."

    return jsonify(response)

if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['RESULTS_FOLDER']):
        os.makedirs(app.config['RESULTS_FOLDER'])
    app.run(debug=True)
