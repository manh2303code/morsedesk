<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE TS>
<TS version="2.1" language="kk_KZ">
<context>
    <name>AboutPage</name>
    <message>
        <location filename="../about_page.py" line="208" />
        <source>Turns Morse code audio into text in English, Russian and Kazakh, and text back into Morse. Nothing leaves this computer.</source>
        <translation>Морзе әліпбиінің дыбысын ағылшын, орыс және қазақ тілдеріндегі мәтінге, ал мәтінді қайтадан Морзе белгілеріне айналдырады. Ешқандай дерек бұл компьютерден шықпайды.</translation>
    </message>
    <message>
        <location filename="../about_page.py" line="211" />
        <source>Technical documentation</source>
        <translation>Техникалық құжаттама</translation>
    </message>
    <message>
        <location filename="../about_page.py" line="212" />
        <source>Version {app}, acoustic model {model}</source>
        <translation>Нұсқа {app}, акустикалық модель {model}</translation>
    </message>
</context>
<context>
    <name>BusyOverlay</name>
    <message>
        <location filename="../widgets/busy_overlay.py" line="76" />
        <location filename="../widgets/busy_overlay.py" line="82" />
        <location filename="../widgets/busy_overlay.py" line="91" />
        <source>Reading the signal…</source>
        <translation>Сигнал оқылуда…</translation>
    </message>
    <message>
        <location filename="../widgets/busy_overlay.py" line="84" />
        <source>Choosing the most likely text with the language model…</source>
        <translation>Тілдік модель ең ықтимал мәтінді таңдап жатыр…</translation>
    </message>
    <message>
        <location filename="../widgets/busy_overlay.py" line="86" />
        <source>Finishing…</source>
        <translation>Аяқталуда…</translation>
    </message>
    <message>
        <location filename="../widgets/busy_overlay.py" line="89" />
        <source>The result appears when the language model has finished.</source>
        <translation>Нәтиже тілдік модель жұмысын аяқтағанда шығады.</translation>
    </message>
</context>
<context>
    <name>DecodePage</name>
    <message>
        <location filename="../decode_page.py" line="342" />
        <source>Hide plain text</source>
        <translation>Қарапайым мәтінді жасыру</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="342" />
        <source>Show plain text</source>
        <translation>Қарапайым мәтінді көрсету</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="343" />
        <source>Plain text to select and copy, and the alternative result</source>
        <translation>Белгілеп көшіруге арналған қарапайым мәтін және балама нәтиже</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="405" />
        <location filename="../decode_page.py" line="753" />
        <source>Open audio file</source>
        <translation>Аудиофайлды ашу</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="407" />
        <source>Audio files ({exts})</source>
        <translation>Аудиофайлдар ({exts})</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="516" />
        <source>Cannot load audio for playback: {detail}</source>
        <translation>Ойнату үшін дыбысты жүктеу мүмкін емес: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="545" />
        <source>{tone} Hz ± 250 Hz</source>
        <translation>{tone} Гц ± 250 Гц</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="589" />
        <source>Model result: {text}</source>
        <translation>Модель нәтижесі: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="590" />
        <source>DSP fallback result: {text}</source>
        <translation>DSP қосалқы нәтижесі: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="601" />
        <source>No Morse signal found in this audio.</source>
        <translation>Бұл аудиода Морзе сигналы табылмады.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="603" />
        <source>Tone not detected clearly; guessing from the spectral peak, so the result may be wrong.</source>
        <translation>Тон анық анықталмады; спектр шыңы бойынша болжанды, сондықтан нәтиже қате болуы мүмкін.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="606" />
        <source>A second tone was found at {second_hz:.0f} Hz; tracking {tracked_hz:.0f} Hz.</source>
        <translation>{second_hz:.0f} Гц жиілігінде екінші тон табылды; {tracked_hz:.0f} Гц бақылануда.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="608" />
        <source>Low confidence.</source>
        <translation>Сенімділік төмен.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="610" />
        <source>Low confidence; the DSP decoder result is shown too.</source>
        <translation>Сенімділік төмен; DSP декодерінің нәтижесі де көрсетілген.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="628" />
        <source>File not found: {path}</source>
        <translation>Файл табылмады: {path}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="630" />
        <source>Cannot read {path}. Supported formats: {exts}</source>
        <translation>{path} оқылмады. Қолдау көрсетілетін пішімдер: {exts}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="634" />
        <source>{path} is {minutes} min long; this version supports up to {limit} min.</source>
        <translation>{path} ұзақтығы {minutes} мин; бұл нұсқа {limit} мин дейін қолдайды.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="636" />
        <source>Setup problem: a model or language model file is missing or unusable.</source>
        <translation>Орнату мәселесі: модель немесе тіл моделі файлы жоқ не жарамсыз.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="637" />
        <source>Internal error while decoding. See the log file for details.</source>
        <translation>Декодтау кезінде ішкі қате. Толығырақ журнал файлында.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="704" />
        <source>Decoding cancelled.</source>
        <translation>Декодтау тоқтатылды.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="721" />
        <source>Text files (*.txt)</source>
        <translation>Мәтін файлдары (*.txt)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="721" />
        <source>JSON files (*.json)</source>
        <translation>JSON файлдары (*.json)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="722" />
        <location filename="../decode_page.py" line="771" />
        <source>Export</source>
        <translation>Экспорттау</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="736" />
        <source>Cannot write {path}: {detail}</source>
        <translation>{path} жазылмады: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="752" />
        <source>Open audio file… (Ctrl+O)</source>
        <translation>Аудиофайлды ашу… (Ctrl+O)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="770" />
        <source>Export to a file: text or JSON with timings</source>
        <translation>Файлға экспорттау: мәтін немесе уақыт белгілері бар JSON</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="772" />
        <source>Text file (.txt)…</source>
        <translation>Мәтіндік файл (.txt)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="773" />
        <source>JSON with word timings (.json)…</source>
        <translation>Әр сөздің уақыты бар JSON (.json)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="774" />
        <source>Decoded text</source>
        <translation>Декодталған мәтін</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="754" />
        <source>Message language:</source>
        <translation>Хабарлама тілі:</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="756" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="757" />
        <location filename="../decode_page.py" line="784" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="758" />
        <location filename="../decode_page.py" line="784" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="759" />
        <location filename="../decode_page.py" line="784" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="763" />
        <source>Use language model</source>
        <translation>Тіл моделін қолдану</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="764" />
        <source>Auto always uses the language model.</source>
        <translation>«Авто» режимі әрқашан тіл моделін пайдаланады.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="766" />
        <source>Decode</source>
        <translation>Декодтау</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="767" />
        <source>Cancel</source>
        <translation>Бас тарту</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="768" />
        <source>Copy the decoded text</source>
        <translation>Декодталған мәтінді көшіру</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="769" />
        <source>Copy</source>
        <translation>Көшіру</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="777" />
        <source>No file selected. Drop an audio file here.</source>
        <translation>Файл таңдалмаған. Аудиофайлды осында сүйреп апарыңыз.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="778" />
        <source>Sample</source>
        <translation>Үлгі</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="779" />
        <source>Signal</source>
        <translation>Сигнал</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="780" />
        <source>3D</source>
        <translation>3D</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="781" />
        <source>Spectrogram</source>
        <translation>Спектрограмма</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="782" />
        <source>Open or drop an audio file to see its signal in 3D.</source>
        <translation>Сигналын 3D түрінде көру үшін аудиофайлды ашыңыз немесе осында сүйреңіз.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="783" />
        <source>Read as:</source>
        <translation>Былай оқу:</translation>
    </message>
</context>
<context>
    <name>EncodePage</name>
    <message>
        <location filename="../encode_page.py" line="357" />
        <source>Estimated audio is {minutes} min long; the limit is {limit} min. Shorten the text or raise the speed.</source>
        <translation>Аудионың болжамды ұзақтығы {minutes} мин, шегі {limit} мин. Мәтінді қысқартыңыз немесе жылдамдықты арттырыңыз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="427" />
        <source>Invalid timing settings: the Farnsworth speed must not exceed the speed in WPM.</source>
        <translation>Тайминг параметрлері қате: Фарнсворт жылдамдығы WPM жылдамдығынан аспауы тиіс.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="430" />
        <source>Could not build the audio.</source>
        <translation>Аудионы құру мүмкін болмады.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="451" />
        <source>Save audio</source>
        <translation>Аудионы сақтау</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="451" />
        <source>Audio ({ext})</source>
        <translation>Аудио ({ext})</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="477" />
        <source>Cannot write {path}: {detail}</source>
        <translation>{path} жазылмады: {detail}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="486" />
        <source>Text to encode</source>
        <translation>Кодталатын мәтін</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="487" />
        <source>Morse code:</source>
        <translation>Морзе коды:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="492" />
        <source>Type text to see its Morse code.</source>
        <translation>Морзе кодын көру үшін мәтін теріңіз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="276" />
        <location filename="../encode_page.py" line="493" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="276" />
        <location filename="../encode_page.py" line="494" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="276" />
        <location filename="../encode_page.py" line="494" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="278" />
        <source>Detected alphabet: {name}</source>
        <translation>Анықталған әліпби: {name}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="303" />
        <location filename="../encode_page.py" line="421" />
        <source>Cannot encode {chars} — fix the text or switch alphabet before sending.</source>
        <translation>{chars} кодтау мүмкін емес — жіберер алдында мәтінді түзетіңіз немесе әліпбиді ауыстырыңыз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="342" />
        <source>Length ≈ {t}</source>
        <translation>Ұзақтығы ≈ {t}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="488" />
        <source>The message appears here as signal-lamp marks.</source>
        <translation>Хабар осында сигнал шамдары түрінде көрінеді.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="489" />
        <source>Alphabet</source>
        <translation>Әліпби</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="489" />
        <source>Timing</source>
        <translation>Тайминг</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="490" />
        <source>Sound</source>
        <translation>Дыбыс</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="490" />
        <source>File</source>
        <translation>Файл</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="493" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="501" />
        <source>Profile:</source>
        <translation>Профиль:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="502" />
        <source>Speed (WPM):</source>
        <translation>Жылдамдық (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="503" />
        <source>Farnsworth (WPM):</source>
        <translation>Фарнсворт (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="504" />
        <source>Weight:</source>
        <translation>Салмақ:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="505" />
        <source>Tone (Hz):</source>
        <translation>Тон (Гц):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="506" />
        <source>Add noise, SNR (dB):</source>
        <translation>Шу қосу, SNR (дБ):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="507" />
        <source>Format:</source>
        <translation>Пішім:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="512" />
        <source>Play</source>
        <translation>Ойнату</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="513" />
        <source>Stop</source>
        <translation>Тоқтату</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="514" />
        <source>Save…</source>
        <translation>Сақтау…</translation>
    </message>
</context>
<context>
    <name>LivePage</name>
    <message>
        <location filename="../live_page.py" line="181" />
        <source>No input device found. Plug in a sound card or check that PortAudio is installed.</source>
        <translation>Кіріс құрылғысы табылмады. Дыбыс картасын қосыңыз немесе PortAudio орнатылғанын тексеріңіз.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>dB</source>
        <translation>дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>WPM</source>
        <translation>WPM</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="211" />
        <location filename="../live_page.py" line="298" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="211" />
        <location filename="../live_page.py" line="298" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="211" />
        <location filename="../live_page.py" line="299" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="220" />
        <source>WPM {v:.1f}</source>
        <translation>Сөз/мин {v:.1f}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="222" />
        <source>Tone {v:.0f} Hz</source>
        <translation>Тон {v:.0f} Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="224" />
        <source>SNR {v:.1f} dB</source>
        <translation>СШҚ {v:.1f} дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="227" />
        <source>Alphabet: {v}</source>
        <translation>Әліпби: {v}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="228" />
        <source>{v:.0f} s heard</source>
        <translation>{v:.0f} с қабылданды</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="243" />
        <source>Listening failed: {detail}</source>
        <translation>Тыңдау сәтсіз аяқталды: {detail}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="293" />
        <source>Input:</source>
        <translation>Кіріс:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="294" />
        <source>Alphabet:</source>
        <translation>Әліпби:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="296" />
        <source>Auto detects the alphabet from the message itself</source>
        <translation>«Авто» әліпбиді хабардың өзінен анықтайды</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="297" />
        <source>Refresh</source>
        <translation>Жаңарту</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="298" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="302" />
        <source>Look for newly plugged devices</source>
        <translation>Жаңа қосылған құрылғыларды іздеу</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="303" />
        <source>Stop</source>
        <translation>Тоқтату</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="303" />
        <source>Listen</source>
        <translation>Тыңдау</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="304" />
        <source>Input level</source>
        <translation>Кіріс сигналының деңгейі</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="305" />
        <source>Level</source>
        <translation>Деңгей</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="306" />
        <source>Alphabet</source>
        <translation>Әліпби</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="307" />
        <source>Tone</source>
        <translation>Тон</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="308" />
        <source>Speed</source>
        <translation>Жылдамдық</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="309" />
        <source>SNR</source>
        <translation>SNR</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="310" />
        <source>Heard</source>
        <translation>Тыңдалды</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="311" />
        <source>Press Listen to see the band live in 3D.</source>
        <translation>Жолақты нақты уақытта 3D түрінде көру үшін «Тыңдау» батырмасын басыңыз.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="312" />
        <source>0–2000 Hz, newest in front</source>
        <translation>0–2000 Гц, ең жаңасы алдында</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="313" />
        <source>Decoded text appears here as it is heard.</source>
        <translation>Декодталған мәтін қабылдануына қарай осында шығады.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="314" />
        <source>Grey text may still change; plain text is final.</source>
        <translation>Сұр мәтін әлі өзгеруі мүмкін; кәдімгі мәтін — түпкілікті.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="315" />
        <source>Copy the decoded text</source>
        <translation>Декодталған мәтінді көшіру</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="316" />
        <source>Copy</source>
        <translation>Көшіру</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="317" />
        <source>Clear the text and start over</source>
        <translation>Мәтінді тазалап, қайта бастау</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="318" />
        <source>Clear</source>
        <translation>Тазалау</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../main_window.py" line="147" />
        <source>MorseDesk</source>
        <translation>MorseDesk</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="148" />
        <source>UI language:</source>
        <translation>Интерфейс тілі:</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="153" />
        <source>Decode</source>
        <translation>Декодтау</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="155" />
        <source>Listen</source>
        <translation>Тыңдау</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="157" />
        <source>Encode</source>
        <translation>Кодтау</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="159" />
        <source>About</source>
        <translation>Бағдарлама туралы</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="161" />
        <source>Settings</source>
        <translation>Параметрлер</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="200" />
        <source>Finishing the current decode; the window will close right after.</source>
        <translation>Ағымдағы декодтау аяқталуда; содан кейін терезе жабылады.</translation>
    </message>
</context>
<context>
    <name>PlayerBar</name>
    <message>
        <location filename="../widgets/player_bar.py" line="221" />
        <source>Pause</source>
        <translation>Кідірту</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="221" />
        <source>Play</source>
        <translation>Ойнату</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="223" />
        <source>Pause playback</source>
        <translation>Ойнатуды кідірту</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="223" />
        <source>Listen to the decoded audio</source>
        <translation>Декодталған дыбысты тыңдау</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="224" />
        <source>Drag to jump to a moment</source>
        <translation>Белгілі бір сәтке өту үшін сүйреңіз</translation>
    </message>
</context>
<context>
    <name>SettingsPage</name>
    <message>
        <location filename="../settings_page.py" line="101" />
        <source>MP3 export: available through libsndfile (built-in LAME).</source>
        <translation>MP3 экспорты: libsndfile арқылы қолжетімді (кірістірілген LAME).</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="103" />
        <source>MP3 export: available through the external ffmpeg command.</source>
        <translation>MP3 экспорты: сыртқы ffmpeg командасы арқылы қолжетімді.</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="105" />
        <source>MP3 export: NOT available. libsndfile here has no LAME encoder and ffmpeg is not on PATH; install ffmpeg or export another format.</source>
        <translation>MP3 экспорты: ҚОЛЖЕТІМСІЗ. Мұндағы libsndfile-де LAME кодері жоқ, ffmpeg те PATH-та жоқ; ffmpeg орнатыңыз немесе басқа пішімді таңдаңыз.</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="112" />
        <source>Decoding engine: {engine}</source>
        <translation>Декодтау қозғалтқышы: {engine}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="114" />
        <source>Other formats written directly: {exts}</source>
        <translation>Тікелей жазылатын басқа пішімдер: {exts}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="115" />
        <source>Log file: {path}</source>
        <translation>Журнал файлы: {path}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="129" />
        <source>version {v}</source>
        <translation>{v} нұсқасы</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="131" />
        <source>{n} parameters</source>
        <translation>{n} параметр</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="133" />
        <source>Decoding engine</source>
        <translation>Декодтау қозғалтқышы</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="134" />
        <source>Acoustic model</source>
        <translation>Акустикалық модель</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="135" />
        <source>Language models</source>
        <translation>Тілдік модельдер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="135" />
        <location filename="../settings_page.py" line="138" />
        <source>none found</source>
        <translation>табылмады</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="136" />
        <source>MP3 export</source>
        <translation>MP3 экспорты</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="137" />
        <source>Formats written directly</source>
        <translation>Тікелей жазылатын пішімдер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="138" />
        <source>Sound inputs</source>
        <translation>Дыбыс кірістері</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="139" />
        <source>Log file</source>
        <translation>Журнал файлы</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="144" />
        <source>Neural network (ONNX) with the classic DSP decoder</source>
        <translation>Нейрондық желі (ONNX) және классикалық DSP декодері</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="145" />
        <source>Classic DSP decoder only</source>
        <translation>Тек классикалық DSP декодері</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="156" />
        <source>This computer</source>
        <translation>Осы компьютер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="160" />
        <source>Open log folder</source>
        <translation>Журнал қалтасын ашу</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="161" />
        <source>Copy report</source>
        <translation>Есепті көшіру</translation>
    </message>
</context>
<context>
    <name>SpectrogramView</name>
    <message>
        <location filename="../widgets/spectrogram.py" line="50" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../widgets/spectrogram.py" line="51" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
</context>
<context>
    <name>StatsBar</name>
    <message>
        <location filename="../widgets/stats_bar.py" line="87" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="88" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="89" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="90" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="93" />
        <source>not detected</source>
        <translation>анықталмады</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="126" />
        <source>Language</source>
        <translation>Тіл</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="127" />
        <source>Tone</source>
        <translation>Тон</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="128" />
        <source>Speed</source>
        <translation>Жылдамдық</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="129" />
        <source>SNR</source>
        <translation>SNR</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="130" />
        <source>Decoded by</source>
        <translation>Декодер</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="131" />
        <source>Took</source>
        <translation>Уақыты</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="134" />
        <source>No result yet.</source>
        <translation>Нәтиже әлі жоқ.</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="141" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="142" />
        <source>dB</source>
        <translation>дБ</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="143" />
        <source>WPM</source>
        <translation>WPM</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="144" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="149" />
        <source>classic DSP</source>
        <translation>классикалық DSP</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="149" />
        <source>neural model</source>
        <translation>нейрондық модель</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="153" />
        <source>{lang} (auto)</source>
        <translation>{lang} (авто)</translation>
    </message>
</context>
<context>
    <name>TechDocWindow</name>
    <message>
        <location filename="../doc_window.py" line="139" />
        <source>MorseDesk technical reference</source>
        <translation>MorseDesk техникалық сипаттамасы</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="142" />
        <location filename="../doc_window.py" line="150" />
        <source>Save as PDF…</source>
        <translation>PDF ретінде сақтау…</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="151" />
        <source>PDF files (*.pdf)</source>
        <translation>PDF файлдары (*.pdf)</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="163" />
        <source>Saved {path}</source>
        <translation>Сақталды: {path}</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="164" />
        <source>Could not save {path}</source>
        <translation>{path} сақталмады</translation>
    </message>
</context>
<context>
    <name>WordView</name>
    <message>
        <location filename="../widgets/word_view.py" line="303" />
        <source>confidence {conf:.2f} · {start:.2f}–{end:.2f} s</source>
        <translation>сенімділік {conf:.2f} · {start:.2f}–{end:.2f} с</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="407" />
        <source>Words appear here as they are heard.</source>
        <translation>Сөздер қабылданған сайын осында шығады.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="408" />
        <source>Open an audio file to decode.</source>
        <translation>Декодтау үшін аудиофайлды ашыңыз.</translation>
    </message>
</context>
</TS>