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
        <location filename="../decode_page.py" line="316" />
        <source>Plain text to select and copy, and the alternative result</source>
        <translation>Белгілеп көшіруге арналған қарапайым мәтін және балама нәтиже</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="372" />
        <location filename="../decode_page.py" line="682" />
        <source>Open audio file</source>
        <translation>Аудиофайлды ашу</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="374" />
        <source>Audio files ({exts})</source>
        <translation>Аудиофайлдар ({exts})</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="476" />
        <source>Cannot load audio for playback: {detail}</source>
        <translation>Ойнату үшін дыбысты жүктеу мүмкін емес: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="517" />
        <source>Model result: {text}</source>
        <translation>Модель нәтижесі: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="518" />
        <source>DSP fallback result: {text}</source>
        <translation>DSP қосалқы нәтижесі: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="529" />
        <source>No Morse signal found in this audio.</source>
        <translation>Бұл аудиода Морзе сигналы табылмады.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="531" />
        <source>Tone not detected clearly; guessing from the spectral peak, so the result may be wrong.</source>
        <translation>Тон анық анықталмады; спектр шыңы бойынша болжанды, сондықтан нәтиже қате болуы мүмкін.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="534" />
        <source>A second tone was found at {second_hz:.0f} Hz; tracking {tracked_hz:.0f} Hz.</source>
        <translation>{second_hz:.0f} Гц жиілігінде екінші тон табылды; {tracked_hz:.0f} Гц бақылануда.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="536" />
        <source>Low confidence.</source>
        <translation>Сенімділік төмен.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="538" />
        <source>Low confidence; the DSP decoder result is shown too.</source>
        <translation>Сенімділік төмен; DSP декодерінің нәтижесі де көрсетілген.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="560" />
        <source>File not found: {path}</source>
        <translation>Файл табылмады: {path}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="562" />
        <source>Cannot read {path}. Supported formats: {exts}</source>
        <translation>{path} оқылмады. Қолдау көрсетілетін пішімдер: {exts}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="566" />
        <source>{path} is {minutes} min long; this version supports up to {limit} min.</source>
        <translation>{path} ұзақтығы {minutes} мин; бұл нұсқа {limit} мин дейін қолдайды.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="568" />
        <source>Setup problem: a model or language model file is missing or unusable.</source>
        <translation>Орнату мәселесі: модель немесе тіл моделі файлы жоқ не жарамсыз.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="569" />
        <source>Internal error while decoding. See the log file for details.</source>
        <translation>Декодтау кезінде ішкі қате. Толығырақ журнал файлында.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="633" />
        <source>Decoding cancelled.</source>
        <translation>Декодтау тоқтатылды.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="650" />
        <source>Text files (*.txt)</source>
        <translation>Мәтін файлдары (*.txt)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="650" />
        <source>JSON files (*.json)</source>
        <translation>JSON файлдары (*.json)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="651" />
        <location filename="../decode_page.py" line="700" />
        <source>Export</source>
        <translation>Экспорттау</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="665" />
        <source>Cannot write {path}: {detail}</source>
        <translation>{path} жазылмады: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="681" />
        <source>Open audio file… (Ctrl+O)</source>
        <translation>Аудиофайлды ашу… (Ctrl+O)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="699" />
        <source>Export to a file: text or JSON with timings</source>
        <translation>Файлға экспорттау: мәтін немесе уақыт белгілері бар JSON</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="701" />
        <source>Text file (.txt)…</source>
        <translation>Мәтіндік файл (.txt)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="702" />
        <source>JSON with word timings (.json)…</source>
        <translation>Әр сөздің уақыты бар JSON (.json)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="703" />
        <source>Decoded text</source>
        <translation>Декодталған мәтін</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="711" />
        <source>Open or drop an audio file to see its spectrogram.</source>
        <translation>Спектрограммасын көру үшін аудиофайлды ашыңыз немесе осында сүйреңіз.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="683" />
        <source>Message language:</source>
        <translation>Хабарлама тілі:</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="315" />
        <source>Hide</source>
        <translation>Жасыру</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="315" />
        <source>Show</source>
        <translation>Көрсету</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="541" />
        <source>Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: MorseDesk decodes Morse sent as a tone (radio CW); key clicks cannot be decoded yet.</source>
        <translation>Тек шыртыл естіледі, Морзе тоны жоқ. Егер бұл телеграф кілті немесе клопфер болса: MorseDesk тонмен берілген Морзені (радио CW) декодтайды; кілт шыртылын әзірге декодтай алмайды.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="685" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="686" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="687" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="688" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="692" />
        <source>Use language model</source>
        <translation>Тіл моделін қолдану</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="693" />
        <source>Auto always uses the language model.</source>
        <translation>«Авто» режимі әрқашан тіл моделін пайдаланады.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="695" />
        <source>Decode</source>
        <translation>Декодтау</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="696" />
        <source>Cancel</source>
        <translation>Бас тарту</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="697" />
        <source>Copy the decoded text</source>
        <translation>Декодталған мәтінді көшіру</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="698" />
        <source>Copy</source>
        <translation>Көшіру</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="704" />
        <source>Plain text</source>
        <translation>Қарапайым мәтін</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="707" />
        <source>No file selected. Drop an audio file here.</source>
        <translation>Файл таңдалмаған. Аудиофайлды осында сүйреп апарыңыз.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="708" />
        <source>Sample</source>
        <translation>Үлгі</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="709" />
        <source>Signal</source>
        <translation>Сигнал</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="710" />
        <source>Open or drop an audio file to see its signal in 3D.</source>
        <translation>Сигналын 3D түрінде көру үшін аудиофайлды ашыңыз немесе осында сүйреңіз.</translation>
    </message>
</context>
<context>
    <name>EncodePage</name>
    <message>
        <location filename="../encode_page.py" line="432" />
        <source>Estimated audio is {minutes} min long; the limit is {limit} min. Shorten the text or raise the speed.</source>
        <translation>Аудионың болжамды ұзақтығы {minutes} мин, шегі {limit} мин. Мәтінді қысқартыңыз немесе жылдамдықты арттырыңыз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="502" />
        <source>Invalid timing settings: the Farnsworth speed must not exceed the speed in WPM.</source>
        <translation>Тайминг параметрлері қате: Фарнсворт жылдамдығы WPM жылдамдығынан аспауы тиіс.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="505" />
        <source>Could not build the audio.</source>
        <translation>Аудионы құру мүмкін болмады.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="589" />
        <source>Save audio</source>
        <translation>Аудионы сақтау</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="589" />
        <source>Audio ({ext})</source>
        <translation>Аудио ({ext})</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="616" />
        <source>Cannot write {path}: {detail}</source>
        <translation>{path} жазылмады: {detail}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="625" />
        <source>Text to encode</source>
        <translation>Кодталатын мәтін</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="626" />
        <source>Morse code:</source>
        <translation>Морзе коды:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="631" />
        <source>Type text to see its Morse code.</source>
        <translation>Морзе кодын көру үшін мәтін теріңіз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="306" />
        <location filename="../encode_page.py" line="632" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="306" />
        <location filename="../encode_page.py" line="633" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="306" />
        <location filename="../encode_page.py" line="633" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="308" />
        <source>Detected alphabet: {name}</source>
        <translation>Анықталған әліпби: {name}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="362" />
        <location filename="../encode_page.py" line="496" />
        <source>Cannot encode {chars} — fix the text or switch alphabet before sending.</source>
        <translation>{chars} кодтау мүмкін емес — жіберер алдында мәтінді түзетіңіз немесе әліпбиді ауыстырыңыз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="405" />
        <source>Length ≈ {t}</source>
        <translation>Ұзақтығы ≈ {t}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="627" />
        <source>The message appears here as signal-lamp marks.</source>
        <translation>Хабар осында сигнал шамдары түрінде көрінеді.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="628" />
        <source>Alphabet</source>
        <translation>Әліпби</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="628" />
        <source>Timing</source>
        <translation>Тайминг</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="629" />
        <source>Sound</source>
        <translation>Дыбыс</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="629" />
        <source>File</source>
        <translation>Файл</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="632" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="640" />
        <source>Profile:</source>
        <translation>Профиль:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="641" />
        <source>Speed (WPM):</source>
        <translation>Жылдамдық (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="642" />
        <source>Farnsworth (WPM):</source>
        <translation>Фарнсворт (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="643" />
        <source>Weight:</source>
        <translation>Салмақ:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="644" />
        <source>Tone (Hz):</source>
        <translation>Тон (Гц):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="645" />
        <source>Add noise, SNR (dB):</source>
        <translation>Шу қосу, SNR (дБ):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="646" />
        <source>Format:</source>
        <translation>Пішім:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="651" />
        <source>Play</source>
        <translation>Ойнату</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="652" />
        <source>Click a letter to play from there.</source>
        <translation>Сол жерден ойнату үшін әріпті басыңыз.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="653" />
        <source>The key presses in time with the sound when you press Play.</source>
        <translation>«Ойнату» басылғанда кілт дыбыспен бірге басылады.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="656" />
        <source>Stop</source>
        <translation>Тоқтату</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="657" />
        <source>Save…</source>
        <translation>Сақтау…</translation>
    </message>
</context>
<context>
    <name>LivePage</name>
    <message>
        <location filename="../live_page.py" line="203" />
        <source>No input device found. Plug in a sound card or check that PortAudio is installed.</source>
        <translation>Кіріс құрылғысы табылмады. Дыбыс картасын қосыңыз немесе PortAudio орнатылғанын тексеріңіз.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="233" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="233" />
        <source>dB</source>
        <translation>дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="233" />
        <source>WPM</source>
        <translation>WPM</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="233" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="238" />
        <location filename="../live_page.py" line="369" />
        <source>English</source>
        <translation>Ағылшын</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="238" />
        <location filename="../live_page.py" line="369" />
        <source>Russian</source>
        <translation>Орыс</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="238" />
        <location filename="../live_page.py" line="370" />
        <source>Kazakh</source>
        <translation>Қазақ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="247" />
        <source>WPM {v:.1f}</source>
        <translation>Сөз/мин {v:.1f}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="249" />
        <source>Tone {v:.0f} Hz</source>
        <translation>Тон {v:.0f} Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="251" />
        <source>SNR {v:.1f} dB</source>
        <translation>СШҚ {v:.1f} дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="254" />
        <source>Alphabet: {v}</source>
        <translation>Әліпби: {v}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="255" />
        <source>{v:.0f} s heard</source>
        <translation>{v:.0f} с қабылданды</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="277" />
        <source>Listening failed: {detail}</source>
        <translation>Тыңдау сәтсіз аяқталды: {detail}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="337" />
        <source>Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: MorseDesk decodes Morse sent as a tone (radio CW); key clicks cannot be decoded yet.</source>
        <translation>Тек шыртыл естіледі, Морзе тоны жоқ. Егер бұл телеграф кілті немесе клопфер болса: MorseDesk тонмен берілген Морзені (радио CW) декодтайды; кілт шыртылын әзірге декодтай алмайды.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="364" />
        <source>Input:</source>
        <translation>Кіріс:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="365" />
        <source>Alphabet:</source>
        <translation>Әліпби:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="367" />
        <source>Auto detects the alphabet from the message itself</source>
        <translation>«Авто» әліпбиді хабардың өзінен анықтайды</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="368" />
        <source>Refresh</source>
        <translation>Жаңарту</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="369" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="373" />
        <source>Look for newly plugged devices</source>
        <translation>Жаңа қосылған құрылғыларды іздеу</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="374" />
        <source>Stop</source>
        <translation>Тоқтату</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="374" />
        <source>Listen</source>
        <translation>Тыңдау</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="375" />
        <source>Input level</source>
        <translation>Кіріс сигналының деңгейі</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="376" />
        <source>Level</source>
        <translation>Деңгей</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="377" />
        <source>Alphabet</source>
        <translation>Әліпби</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="378" />
        <source>Tone</source>
        <translation>Тон</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="379" />
        <source>Speed</source>
        <translation>Жылдамдық</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="380" />
        <source>SNR</source>
        <translation>SNR</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="381" />
        <source>Heard</source>
        <translation>Тыңдалды</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="382" />
        <source>Signal</source>
        <translation>Сигнал</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="383" />
        <source>Press Listen to see the band live in 3D.</source>
        <translation>Жолақты нақты уақытта 3D түрінде көру үшін «Тыңдау» батырмасын басыңыз.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="384" />
        <source>Press Listen to see the band live.</source>
        <translation>Жолақты нақты уақытта көру үшін «Тыңдау» батырмасын басыңыз.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="386" />
        <source>Grey words may still change. Underlined words are uncertain; point at any word for details.</source>
        <translation>Сұр сөздер әлі өзгеруі мүмкін. Асты сызылған сөздер күмәнді; толығырақ білу үшін сөзге меңзерді апарыңыз.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="390" />
        <source>Copy the decoded text</source>
        <translation>Декодталған мәтінді көшіру</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="391" />
        <source>Copy</source>
        <translation>Көшіру</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="392" />
        <source>Clear the text and start over</source>
        <translation>Мәтінді тазалап, қайта бастау</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="393" />
        <source>Clear</source>
        <translation>Тазалау</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../main_window.py" line="148" />
        <source>MorseDesk</source>
        <translation>MorseDesk</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="149" />
        <source>UI language:</source>
        <translation>Интерфейс тілі:</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="154" />
        <source>Decode</source>
        <translation>Декодтау</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="156" />
        <source>Listen</source>
        <translation>Тыңдау</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="158" />
        <source>Encode</source>
        <translation>Кодтау</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="160" />
        <source>About</source>
        <translation>Бағдарлама туралы</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="162" />
        <source>Settings</source>
        <translation>Параметрлер</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="201" />
        <source>Finishing the current decode; the window will close right after.</source>
        <translation>Ағымдағы декодтау аяқталуда; содан кейін терезе жабылады.</translation>
    </message>
</context>
<context>
    <name>PlayerBar</name>
    <message>
        <location filename="../widgets/player_bar.py" line="266" />
        <location filename="../widgets/player_bar.py" line="267" />
        <source>Unmute</source>
        <translation>Дыбысты қосу</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="266" />
        <location filename="../widgets/player_bar.py" line="267" />
        <source>Mute</source>
        <translation>Дыбысты өшіру</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="268" />
        <source>Volume: {v} %</source>
        <translation>Дыбыс деңгейі: {v} %</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="269" />
        <source>Volume</source>
        <translation>Дыбыс деңгейі</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="304" />
        <source>Pause</source>
        <translation>Кідірту</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="304" />
        <source>Play</source>
        <translation>Ойнату</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="306" />
        <source>Pause playback</source>
        <translation>Ойнатуды кідірту</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="306" />
        <source>Listen to the decoded audio</source>
        <translation>Декодталған дыбысты тыңдау</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="307" />
        <source>Drag to jump to a moment</source>
        <translation>Белгілі бір сәтке өту үшін сүйреңіз</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="308" />
        <source>Playback speed (the pitch stays the same)</source>
        <translation>Ойнату жылдамдығы (дыбыс биіктігі өзгермейді)</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="309" />
        <source>Playback speed</source>
        <translation>Ойнату жылдамдығы</translation>
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
    <name>SignalPanel</name>
    <message>
        <location filename="../widgets/signal_panel.py" line="298" />
        <source>{tone} Hz ± 250 Hz</source>
        <translation>{tone} Гц ± 250 Гц</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="329" />
        <source>{db:+.0f} dB above noise</source>
        <translation>{db:+.0f} дБ шудан жоғары</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="332" />
        <source>{t:.1f} s ago</source>
        <translation>{t:.1f} с бұрын</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="341" />
        <source>Back to live</source>
        <translation>Тікелей эфирге</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="342" />
        <source>Follow playback</source>
        <translation>Дыбысқа ілесу</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="345" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="345" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="346" />
        <source>3D</source>
        <translation>3D</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="347" />
        <source>Spectrogram</source>
        <translation>Спектрограмма</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="348" />
        <source>Show the signal as a 3D landscape</source>
        <translation>Сигналды 3D бедер түрінде көрсету</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="349" />
        <source>Show the signal as a spectrogram</source>
        <translation>Сигналды спектрограмма түрінде көрсету</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="350" />
        <source>The view follows the sound again</source>
        <translation>Көрініс қайтадан дыбысқа ілеседі</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="351" />
        <source>Drag or scroll to look back; click to replay after you stop</source>
        <translation>Артқа қарау үшін сүйреңіз не айналдырыңыз; тоқтатқаннан кейін басып, қайта тыңдаңыз</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="352" />
        <source>Drag or scroll to move, click to listen from there</source>
        <translation>Жылжу үшін сүйреңіз не айналдырыңыз; сол жерден тыңдау үшін басыңыз</translation>
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
        <location filename="../widgets/word_view.py" line="343" />
        <source>high</source>
        <translation>жоғары</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="344" />
        <source>No underline: the decoder was sure of every letter in this word.</source>
        <translation>Асты сызылмаған: декодер бұл сөздің әр әрпіне сенімді болды.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="346" />
        <source>medium</source>
        <translation>орташа</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="347" />
        <source>Yellow underline: the decoder was only fairly sure of some letters in this word.</source>
        <translation>Сары сызық: декодер бұл сөздің кейбір әріптеріне тек ішінара сенімді болды.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="350" />
        <source>low</source>
        <translation>төмен</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="351" />
        <source>Red underline: the decoder was unsure of this word. Check it by ear.</source>
        <translation>Қызыл сызық: декодер бұл сөзге сенімді емес. Оны құлақпен тексеріңіз.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="353" />
        <source>Confidence {value} ({level})</source>
        <translation>Сенімділік {value} ({level})</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="359" />
        <source>In our tests, words at this level were right about {percent} % of the time.</source>
        <translation>Біздің өлшеулерімізде осы деңгейдегі сөздер шамамен {percent} % жағдайда дұрыс болды.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="363" />
        <source>Grey: not final yet. It may still change as more audio arrives.</source>
        <translation>Сұр: әлі түпкілікті емес. Дыбыс келген сайын өзгеруі мүмкін.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="364" />
        <source>{start}–{end} s</source>
        <translation>{start}–{end} с</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="482" />
        <source>Words appear here as they are heard.</source>
        <translation>Сөздер қабылданған сайын осында шығады.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="483" />
        <source>Open an audio file to decode.</source>
        <translation>Декодтау үшін аудиофайлды ашыңыз.</translation>
    </message>
</context>
</TS>