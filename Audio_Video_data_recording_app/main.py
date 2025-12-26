import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import cv2
import pyaudio
import wave
import threading
from pathlib import Path
import json
import pandas as pd
import toml
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

class RecordingApp:
    def __init__(self, root, webcam_id=0, audio_channels=1, transcript_file=''):
        self.root = root
        self.webcam_id = webcam_id
        self.sentences = None
        self.sentence_index = 0
        self.person_index = 0
        self.is_recording = False
        self.cap = None
        self.base_filename = None
        self.video_writer = None
        self.audio_thread = None
        self.audio_frames = []
        self.user_name = None
        self.audio_format = pyaudio.paInt16
        self.audio_channels = audio_channels
        self.audio_rate = 44100
        self.audio_chunk = 1024
        self.stop_event = threading.Event()
        self.error_event = threading.Event()
        self.transcript_file = transcript_file

        self.root.title("Sentence Recording")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Main Frame (Horizontal Layout)
        self.main_frame = tk.Frame(root, padx=20, pady=20)
        self.main_frame.pack(fill="both", expand=True)

        # Left Panel for Video Preview and Sentence Display
        self.left_panel = tk.Frame(self.main_frame, padx=20, pady=20)
        self.left_panel.pack(side="left", fill="both", expand=True, ipadx=100)

        # Sentence Display
        self.sentence_label = tk.Label(
            self.left_panel, text="", wraplength=700,  height=3, width=30,
            justify="left", font=("標楷體", 36, "bold"), background="lightgrey"
        )
        self.sentence_label.pack(ipady=5, ipadx=5, pady=10)
        self.sentence_label.pack_propagate(False)

        self.user_control_frame = tk.Frame(self.left_panel)
        self.user_control_frame.pack(pady=20)
        self.user_control_frame.grid_columnconfigure(0, weight=1)

        self.user_record_button = tk.Button(
            self.user_control_frame, text="Record", font=("微軟正黑體", 16), background="SystemButtonFace",
            foreground="black", command=self.record_button_action, width=6, state="disabled"
        )
        self.user_record_button.grid(row=0, column=0)

        self.user_next_sentence_button = tk.Button(
            self.user_control_frame, text="Next", font=("微軟正黑體", 16), background="SystemButtonFace",
            foreground="black", command=self.next_sentence, state="disabled"
        )
        self.user_next_sentence_button.grid(row=0, column=1, padx=10)


        # Video Preview Canvas
        self.canvas = tk.Canvas(self.left_panel, width=700, height=400, bg="black")
        self.canvas.pack()

        self.status_frame = tk.Frame(self.left_panel, width=700, height=60)
        self.status_frame.pack(pady=10)
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_propagate(False)

        self.sentence_num_label = tk.Label(
            self.status_frame, text="", font=("微軟正黑體", 16)
        )
        self.sentence_num_label.grid(row=0, column=0, sticky="w")

        self.reocrd_status_label = tk.Label(
            self.status_frame, text="", font=("微軟正黑體", 14, "bold"),
            bg="systemButtonFace", fg="white",
        )
        self.reocrd_status_label.grid(row=0, column=1, sticky="e", ipadx=2, ipady=2)

        # Right Panel for Controls
        self.right_panel = tk.Frame(self.main_frame, padx=20, pady=20)
        self.right_panel.pack(side="right", fill="y", padx=20)

        # Title Label
        self.title_label = tk.Label(self.right_panel, text="Recording App", font=("微軟正黑體", 24, "bold"))
        self.title_label.pack(pady=20)
        
        self.transcript_frame = tk.Frame(self.right_panel)
        self.transcript_frame.pack(pady=10, anchor="w")

        # Load Transcript Button
        self.load_button = tk.Button(
            self.transcript_frame,
            text="Load",
            font=("微軟正黑體", 16),
            command=self.open_transcript,
            width=10, pady=10
        )
        self.load_button.grid(row=0, column=0)

        self.edit_button = tk.Button(
            self.transcript_frame,
            text="Edit",
            font=("微軟正黑體", 16),
            state="disabled",
            command=self.edit_sentence,
            width=10, pady=10
        )
        self.edit_button.grid(row=0, column=1, padx=18)

        # User Name
        self.name_frame = tk.Frame(self.right_panel)
        self.name_frame.pack(pady=10, anchor="w")

        self.name_label = tk.Label(self.name_frame, text="Name: ", font=("微軟正黑體", 16))
        self.name_label.grid(row=0, column=0, sticky="w")

        self.name_entry = tk.Entry(self.name_frame, font=("微軟正黑體", 16))
        self.name_entry.grid(row=1, column=0, sticky="w")
        self.name_entry.bind("<Return>", lambda e: self.set_user_name())

        self.set_name_button = tk.Button(
            self.name_frame,
            text="↵",
            font=("微軟正黑體", 10, "bold"),
            command=self.set_user_name,
            width=5, pady=3
        )
        self.set_name_button.grid(row=1, column=2, padx=5)

        # Person Index
        self.person_index_frame = tk.Frame(self.right_panel)
        self.person_index_frame.pack(pady=10, anchor="w")
        self.person_index_frame.grid_columnconfigure(0, weight=1)

        self.person_index_label = tk.Label(self.person_index_frame, text="Person Index :", font=("微軟正黑體", 16), anchor="w")
        self.person_index_label.grid(row=0, column=0, sticky="w")

        self.person_index_entry = tk.Entry(self.person_index_frame, font=("微軟正黑體", 16), width=15)
        self.person_index_entry.grid(row=1, column=0, sticky="w")
        self.person_index_entry.bind("<Return>", lambda e: self.set_person_index())

        self.set_person_index_button = tk.Button(
            self.person_index_frame,
            text="↵",
            font=("微軟正黑體", 10, "bold"),
            state="disabled",
            command=self.set_person_index,
            width=5, pady=3
        )
        self.set_person_index_button.grid(row=1, column=1, padx=5)

        self.person_next_button = tk.Button(
            self.person_index_frame,
            text=">",
            font=("微軟正黑體", 10, "bold"),
            state="disabled",
            command=self.next_person,
            width=5, pady=3
        )
        self.person_next_button.grid(row=1, column=2, padx=5)

        # Sentence Index
        self.index_frame = tk.Frame(self.right_panel)
        self.index_frame.pack(pady=10, anchor="w")
        self.index_frame.grid_columnconfigure(0, weight=1)

        self.index_label = tk.Label(self.index_frame, text="Sentence Index : ", font=("微軟正黑體", 16), anchor="w")
        self.index_label.grid(row=0, column=0, sticky="w")

        self.index_entry = tk.Entry(self.index_frame, font=("微軟正黑體", 16), width=15)
        self.index_entry.grid(row=1, column=0, sticky="w")
        self.index_entry.bind("<Return>", lambda e: self.go_to_sentence())

        self.go_button = tk.Button(
            self.index_frame,
            text="↵",
            font=("微軟正黑體", 10, "bold"),
            state="disabled",
            command=self.go_to_sentence,
            width=5, pady=3
        )
        self.go_button.grid(row=1, column=2, padx=5)

        self.check_button = tk.Button(
            self.index_frame,
            text="?",
            font=("微軟正黑體", 10, "bold"),
            state="disabled",
            command=self.check_completion,
            width=5, pady=3
        )
        self.check_button.grid(row=1, column=3, padx=5)


        self.record_button = tk.Button(
            self.right_panel,
            text="Record",
            font=("微軟正黑體", 16),
            background="SystemButtonFace",
            foreground="black",
            state="disabled",
            command=self.record_button_action,
            width=22, pady=10
        )
        self.record_button.pack(pady=10, anchor="w")

        self.sentence_control_frame = tk.Frame(self.right_panel)
        self.sentence_control_frame.pack(pady=10, anchor="w")

        self.prev_button = tk.Button(
            self.sentence_control_frame,
            text="Previous",
            font=("微軟正黑體", 16),
            state="disabled",
            command=self.prev_sentence,
            width=10, pady=10
        )
        self.prev_button.grid(row=0, column=0)

        self.next_button = tk.Button(
            self.sentence_control_frame,
            text="Next",
            font=("微軟正黑體", 16),
            state="disabled",
            command=self.next_sentence,
            width=10, pady=10
        )
        self.next_button.grid(row=0, column=1, padx=18)

        if self.transcript_file != '':
            self.root.after(100, self.load_transcript)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.stop_event.set()
            self.end_recording()
            self.root.destroy()

    def exit_fullscreen(self, event):
        self.root.attributes("-fullscreen", False)

    def set_user_name(self):
        self.user_name = self.name_entry.get()
        if not self.user_name.strip():
            messagebox.showerror("Error", "Please enter your name!")
        else:
            messagebox.showinfo("Success", f"Name set to {self.user_name}!")
            self.name_label.config(text=f"Name: {self.user_name}")
            self.name_entry.delete(0, tk.END)
            self.update_sentence_label()

    def set_person_index(self):
        try:
            index = int(self.person_index_entry.get()) - 1
            if 0 <= index < len(self.sentences):
                self.person_index = index
                self.sentence_index = 0
                self.update_sentence_label()
                self.prev_button.config(state="disabled")
                self.next_button.config(state="normal")
            else:
                messagebox.showerror("Error", "Person index out of range!")
        except ValueError:
            messagebox.showerror("Error", "Invalid person index!")

    def next_person(self):
        if self.person_index == len(self.sentences) - 1:
            messagebox.showinfo("Done", "No more persons to record!")
            return

        self.person_index += 1
        self.sentence_index = 0
        self.update_sentence_label()
        self.prev_button.config(state="disabled")
        self.next_button.config(state="normal")

    def check_record_status(self):
        self.base_filename = f"data/{self.user_name}/P{self.person_index}_{self.sentence_index + 1}"
        if Path(f"{self.base_filename}.mp4").exists():
            if self.is_recording:
                self.reocrd_status_label.config(text="...Recording", bg="#cda100", fg="white")
            else:
                self.reocrd_status_label.config(text="Recorded", bg="green", fg="white")
        else:
            self.reocrd_status_label.config(text="Not Recorded", bg="red", fg="white")

    def update_sentence_label(self):
        if not self.sentences:
            return

        current_sentence = self.sentences[self.person_index][self.sentence_index]
        self.sentence_label.config(text=f"{current_sentence}")
        self.sentence_num_label.config(text=f"Current Index : {self.sentence_index + 1}/{len(self.sentences[self.person_index])}")


        self.person_index_entry.delete(0, tk.END)
        self.person_index_entry.insert(0, str(self.person_index + 1))

        self.index_entry.delete(0, tk.END)
        self.index_entry.insert(0, str(self.sentence_index + 1))

        self.check_record_status()

    def open_transcript(self):
        file_path = Path(filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")]))
        
        if str(file_path) == ".":
            return
        
        if file_path.suffix != ".json":
            messagebox.showerror("Error", "Please select a JSON file.")
            return
        
        self.transcript_file = file_path
        self.load_transcript()

    def load_transcript(self):
        if not Path(self.transcript_file).exists():
            messagebox.showerror("Error", "Transcript file not found!")
            return

        try:
            with open(self.transcript_file, "r", encoding="utf-8") as f:
                file = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading transcript file: {e}")
            return

        self.sentences = [data for data in file["data"]]
        self.sentence_index = 0
        self.update_sentence_label()

        self.next_button.config(state="normal")
        self.prev_button.config(state="disabled")
        self.user_next_sentence_button.config(state="normal")
        self.edit_button.config(state="normal")
        self.set_person_index_button.config(state="normal")
        self.person_next_button.config(state="normal")
        self.go_button.config(state="normal")
        self.check_button.config(state="normal")
        self.record_button.config(state="normal")
        self.user_record_button.config(state="normal")
        self.name_entry.focus()
        self.index_entry.delete(0, tk.END)
        self.index_entry.insert(0, "1")
        self.person_index_entry.delete(0, tk.END)
        self.person_index_entry.insert(0, "1")
        messagebox.showinfo("Success", "Transcript loaded successfully!")

    def edit_sentence(self):
        sentence = simpledialog.askstring(
            title="Edit Sentence", 
            prompt="Edit the sentence below:",
            initialvalue=self.sentences[self.person_index][self.sentence_index]
        )
        
        if not sentence:
            return
        
        original = self.sentences[self.person_index][self.sentence_index]
        
        # Update original json file
        with open(self.transcript_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data["data"][self.person_index][self.sentence_index] = sentence
        
        with open(self.transcript_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        # Update the output sentence file
        sentence_file = f"{self.base_filename}.txt"
        if Path(sentence_file).exists():
            with open(sentence_file, "w", encoding="utf-8") as f:
                f.write(sentence)
        
        # Update the displayed sentence
        self.sentences[self.person_index][self.sentence_index] = sentence
        self.update_sentence_label()

        # Save the edit to a log file
        log_file = Path("edit_log.csv")
        if log_file.exists():
            df = pd.read_csv(log_file)
        else:
            df = pd.DataFrame(columns=["Time", "User", "Person Index", "Sentence Index", "Original", "Edited"])
        
        new_row = {
            "Time": pd.Timestamp.now(),
            "User": self.user_name or "Unknown",
            "Person Index": self.person_index + 1,
            "Sentence Index": self.sentence_index + 1,
            "Original": original,
            "Edited": sentence
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(log_file, index=False)

        messagebox.showinfo("Success", "Sentence updated successfully!")

    def go_to_sentence(self):
        try:
            index = int(self.index_entry.get()) - 1
            if 0 <= index < len(self.sentences[self.person_index]):
                self.sentence_index = index
                self.update_sentence_label()
            else:
                messagebox.showerror("Error", "Index out of range!")
        except ValueError:
            messagebox.showerror("Error", "Invalid index!")

    def record_button_action(self):
        if self.is_recording:
            self.end_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if not self.user_name:
            messagebox.showerror("Error", "Please set your name before recording!")
            return

        Path(f"data/{self.user_name}").mkdir(exist_ok=True, parents=True)

        self.cap = cv2.VideoCapture(self.webcam_id, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Error opening webcam {self.webcam_id}")
            webcam_id = simpledialog.askinteger("Webcam Index", "Please enter the webcam index:", initialvalue=self.webcam_id)
            if webcam_id is not None:
                self.webcam_id = webcam_id
                with open("config.toml", "r") as f:
                    config = toml.load(f)
                config["webcam"]["index"] = self.webcam_id
                with open("config.toml", "w") as f:
                    toml.dump(config, f)
            return

        # Video output file path
        video_file = f"{self.base_filename}.mp4"
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
        self.video_writer = cv2.VideoWriter(video_file, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

        # Save the sentence to a text file
        sentence_file = f"{self.base_filename}.txt"
        with open(sentence_file, "w", encoding="utf-8") as f:
            f.write(self.sentences[self.person_index][self.sentence_index])

        self.audio_frames = []

        self.stop_event.clear()
        self.error_event.clear()

        # Start recording audio in a separate thread
        self.audio_thread = threading.Thread(target=self.record_audio)
        self.audio_thread.start()

        self.is_recording = True

        self.next_button.config(state="disabled")
        self.record_button.config(text="Stop", background="red", foreground="white")
        self.user_record_button.config(text="Stop", background="red", foreground="white")
        self.check_record_status()
        self.update_frame()


    def record_audio(self):
        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(format=self.audio_format, channels=self.audio_channels,
                            rate=self.audio_rate, input=True, frames_per_buffer=self.audio_chunk)
        except ValueError:
            self.stop_event.set()
            self.error_event.set()

        while not self.stop_event.is_set():
            data = stream.read(self.audio_chunk)
            self.audio_frames.append(data)

        audio.terminate()

        if self.error_event.is_set():
            self.root.after(0, self.end_recording)
            return

        stream.stop_stream()
        stream.close()

        # Save audio to a WAV file
        audio_file = f"{self.base_filename}.wav"
        with wave.open(audio_file, 'wb') as wf:
            wf.setnchannels(self.audio_channels)
            wf.setsampwidth(audio.get_sample_size(self.audio_format))
            wf.setframerate(self.audio_rate)
            wf.writeframes(b''.join(self.audio_frames))

    def end_recording(self):
        self.stop_event.set()  # Signal the audio thread to stop
        # Wait for audio thread to finish
        if self.audio_thread and self.audio_thread.is_alive() and not self.error_event.is_set:
            self.audio_thread.join()

        # Release resources
        if self.cap:
            self.cap.release()
        if self.video_writer:
            self.video_writer.release()

        self.is_recording = False
        self.record_button.config(text="Record", background="SystemButtonFace", foreground="black")
        self.user_record_button.config(text="Record", background="SystemButtonFace", foreground="black")
        self.next_button.config(state="normal")

        # Check for errors
        if self.error_event.is_set():
            for ext in ["mp4", "wav", "txt"]:
                Path(f"{self.base_filename}.{ext}").unlink(missing_ok=True)

            messagebox.showerror("Error", f"Invalid audio channels: {self.audio_channels}")
            channels = simpledialog.askinteger("Audio Channels", "Please enter the number of audio channels:", initialvalue=self.audio_channels)
            if channels is not None:
                self.audio_channels = channels
                with open("config.toml", "r") as f:
                    config = toml.load(f)
                config["audio"]["channels"] = self.audio_channels
                with open("config.toml", "w") as f:
                    toml.dump(config, f)
                    
            self.error_event.clear()
        self.check_record_status()

    def update_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Convert frame to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Write to video if recording
                if self.is_recording:
                    self.video_writer.write(frame)
                # Display on Canvas
                frame_pil = Image.fromarray(frame_rgb)
                frame_pil = frame_pil.resize((600, 450))
                photo = ImageTk.PhotoImage(frame_pil)
                self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, anchor=tk.CENTER, image=photo)
                self.canvas.image = photo  # Keep a reference to prevent garbage collection

        # Schedule next update
        if self.is_recording:
            self.root.after(10, self.update_frame)

    def check_completion(self):
        not_done = []
        for i in range(len(self.sentences[self.person_index])):
            if not Path(f"data/{self.user_name}/P{self.person_index}_{i + 1}.mp4").exists():
                not_done.append(i + 1)
        if not_done:
            messagebox.showwarning("Warning", f"The following sentences are not recorded: \n{not_done}")
        else:
            messagebox.showinfo("Done", "All sentences for {self.user_name} are recorded!")


    def next_sentence(self):

        if self.sentence_index == len(self.sentences[self.person_index]) - 1:
            self.check_completion()
            return

        self.sentence_index += 1

        if self.sentence_index > 0:
            self.prev_button.config(state="normal")

        self.update_sentence_label()  # Update the label to include the index


    def prev_sentence(self):
        self.sentence_index -= 1

        if self.sentence_index == 0:
            self.prev_button.config(state="disabled")

        self.update_sentence_label()



# Main Program
if __name__ == "__main__":
    with open("config.toml", "r") as f:
        config = toml.load(f)

    root = tk.Tk()
    app = RecordingApp(
        root, 
        audio_channels=config["audio"].get("channels", 1),
        webcam_id=config["webcam"].get("index", 0),
        transcript_file=config["transcript"].get("path", '')
    )
    root.mainloop()
