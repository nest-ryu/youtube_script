

\## 🎬 YouTube Script Auto Streamlit



이 앱은 YouTube 영상에서 스크립트(자막) 를 자동 추출하고, 자막이 없을 경우 Whisper 음성 인식 모델로 전사하여 텍스트를 생성합니다. 또한 ffplay 를 이용해 영상의 오디오만 재생할 수 있습니다.



---



\### ⚙️ 주요 기능



\- 🎥 유튜브 영상 링크 입력만으로 자동 스크립트 추출

\- 🧠 자막이 없으면 Whisper(`small` 모델)로 음성 전사

\- 🌐 영어 스크립트일 경우 자동 한국어 번역(`\_translated.txt` 저장)

\- 💾 원문 스크립트 다운로드 (`\_script.txt`)

\- 🔊 ffplay를 이용한 오디오 재생 (영상 없이)

\- 🧩 파일명은 콘텐츠명 기반 자동 지정 (채널명 제외)



---



\### 📦 설치 방법



```bash

pip install -r requirements.txt

```



&nbsp;⚠️ Whisper 사용 시 ffmpeg 설치가 필요합니다.



&nbsp;- Windows httpsffmpeg.orgdownload.html 에서 zip 설치 후 PATH 등록

&nbsp;- macOS `brew install ffmpeg`

&nbsp;- Linux `sudo apt install ffmpeg`

&nbsp;- Android (Pydroid3) `pip install ffmpeg-python`



---



\### 🚀 실행 방법



```bash

streamlit run youtube_script_auto.py

```



앱이 실행되면 웹 브라우저가 자동으로 열리며, 아래 단계를 수행할 수 있습니다

1\. YouTube 영상 링크 입력

2\. (선택) 영상 제목 입력 → 파일명으로 사용됨

3\. \[🚀 스크립트 추출 실행] 버튼 클릭

4\. 결과 확인 및 스크립트 다운로드  오디오 재생



---



\### 🧠 Whisper 모델 참고



&nbsp;모델  속도  정확도  권장 환경 

------------------------------

&nbsp;`tiny`  ⚡ 매우 빠름  ⭐ 낮음  모바일, 테스트 

&nbsp;`base`  빠름  보통  일반 사용 

&nbsp;`small`  중간  높음  한국어영어 혼용 영상 

&nbsp;`medium`  느림  매우 높음  GPU 환경 

&nbsp;`large`  🐢 매우 느림  🧠 최고 정확도  고성능 서버 



---






