# youtube_script_auto.py
# Streamlit 기반 YouTube 스크립트 자동 추출 및 오디오 재생 앱

import os
import re
import subprocess
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
import whisper
import unicodedata
import atexit
import signal
from typing import List, Dict, Optional
from deep_translator import GoogleTranslator
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

# 모든 오디오 프로세스 정리 함수
def cleanup_audio_processes():
    """모든 실행 중인 오디오 프로세스 종료"""
    if 'audio_processes' in st.session_state:
        for video_id, process in list(st.session_state.audio_processes.items()):
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except:
                    try:
                        process.kill()
                    except:
                        pass
        st.session_state.audio_processes.clear()

# 앱 종료 시 자동 정리 등록
atexit.register(cleanup_audio_processes)

# 텍스트 정리 함수
def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 유니코드 정규화 함수
def _normalize_visible_text(text: str) -> str:
    """유니코드 수학 볼드 등 특수 스타일 문자를 일반 문자로 정규화."""
    if not text:
        return ""
    # NFKD 정규화로 호환 분해 후 결합 부호 제거
    decomposed = unicodedata.normalize('NFKD', text)
    without_marks = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
    # 가시성 향상을 위해 공백 정리
    normalized_spaces = re.sub(r"\s+", " ", without_marks).strip()
    return normalized_spaces

# 파일 이름 안전화 함수
def make_filesafe_title(title: str) -> str:
    """Windows에서도 안전한 파일명으로 변환."""
    base = _normalize_visible_text(title) or "script"
    # 금지 문자 제거
    base = re.sub(r"[<>:\\/\\|?*\"]", " ", base)
    # 제어 문자 제거
    base = ''.join(ch for ch in base if ch >= ' ')
    # 앞뒤 공백/점 제거, 연속 공백 축소
    base = re.sub(r"\s+", "_", base).strip().rstrip('_')
    # 길이 제한
    if len(base) > 150:
        base = base[:150].rstrip('_')
    # 빈 문자열 방지
    return base or "script"

# 오디오 다운로드
def download_audio(video_url, filename="audio.mp3"):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return filename

# 유튜브 자막 또는 Whisper로 스크립트 추출
def get_youtube_script(video_url, lang="en", title="content"):
    video_id = video_url.split("v=")[-1].split("&")[0]
    text_result = None

    safe_title = make_filesafe_title(title)

    try:
        transcript_api = YouTubeTranscriptApi()
        fetched_transcript = transcript_api.fetch(video_id, languages=[lang, 'en', 'ko'])
        # FetchedTranscript 객체를 리스트로 변환 (각 항목은 FetchedTranscriptSnippet 객체)
        transcript_list = list(fetched_transcript)
        text_result = " ".join([t.text for t in transcript_list])
        text_result = clean_text(text_result)
    except (TranscriptsDisabled, NoTranscriptFound):
        try:
            audio_file = download_audio(video_url)
            model = whisper.load_model("small")
            result = model.transcribe(audio_file)
            text_result = clean_text(result['text'])
            # 임시 오디오 파일 삭제
            if os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception as e:
            return None
    except Exception as e:
        return None

    # 자동 파일 저장 제거 (원문/번역은 메모리에서만 관리)

    return text_result

# 오디오만 재생
def play_audio_only(video_url):
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        audio_url = info['url']
    
    # FFmpeg 경로 설정
    ffmpeg_path = os.getenv("FFMPEG_PATH", "C:\\ffmpeg")
    ffplay_path = os.path.join(ffmpeg_path, "bin", "ffplay.exe")
    
    # FFplay 실행 파일이 존재하는지 확인
    if not os.path.exists(ffplay_path):
        # bin 폴더가 없으면 직접 경로 확인
        ffplay_path = os.path.join(ffmpeg_path, "ffplay.exe")
        if not os.path.exists(ffplay_path):
            # PATH에서 ffplay 찾기
            ffplay_path = "ffplay"
    
    subprocess.run([ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet", audio_url])

# 채널 영상 목록 가져오기 함수들
def get_channel_videos(channel_name: str, max_results: int = 10) -> List[Dict]:
    """
    채널명으로 최신 영상 목록 가져오기
    
    Args:
        channel_name: 유튜브 채널명
        max_results: 가져올 최대 영상 수
    
    Returns:
        영상 정보 리스트
    """
    search_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            # 방법 1: 채널명으로 검색하여 채널 URL 찾기
            try:
                search_query = f"ytsearch1:{channel_name}"
                info = ydl.extract_info(search_query, download=False)
                
                if info and 'entries' in info and len(info['entries']) > 0:
                    first_result = info['entries'][0]
                    channel_id = first_result.get('channel_id') or first_result.get('channel')
                    channel_name_found = first_result.get('channel')
                    
                    if channel_id or channel_name_found:
                        # 채널 URL 구성
                        if channel_id:
                            if channel_id.startswith('@') or channel_id.startswith('UC'):
                                if channel_id.startswith('@'):
                                    channel_url = f"https://www.youtube.com/{channel_id}/videos"
                                else:
                                    channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
                            else:
                                channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
                        elif channel_name_found:
                            channel_url = f"https://www.youtube.com/c/{channel_name_found}/videos"
                        else:
                            channel_url = None
                        
                        if channel_url:
                            return _get_videos_from_url(channel_url, max_results)
            except Exception as e:
                pass
            
            # 방법 2: 직접 채널 URL 시도
            possible_urls = [
                f"https://www.youtube.com/@{channel_name}/videos",
                f"https://www.youtube.com/c/{channel_name}/videos",
                f"https://www.youtube.com/user/{channel_name}/videos",
                f"https://www.youtube.com/channel/{channel_name}/videos",
            ]
            
            for url in possible_urls:
                try:
                    videos = _get_videos_from_url(url, max_results)
                    if videos:
                        return videos
                except Exception:
                    continue
            
            return []
            
    except Exception as e:
        st.error(f"오류 발생: {e}")
        return []

def _get_videos_from_url(channel_url: str, max_results: int = 10) -> List[Dict]:
    """채널 URL로부터 영상 목록 가져오기"""
    channel_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(channel_opts) as ydl:
            channel_info = ydl.extract_info(channel_url, download=False)
            
            if channel_info and 'entries' in channel_info:
                videos = []
                for i, entry in enumerate(channel_info['entries'][:max_results], 1):
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    title = entry.get('title', '제목 없음')
                    url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
                    duration = entry.get('duration', 0)
                    
                    videos.append({
                        'index': i,
                        'title': title,
                        'url': url,
                        'id': video_id,
                        'duration': duration
                    })
                
                return videos if videos else None
    except Exception as e:
        raise Exception(f"URL에서 영상 목록 가져오기 실패: {e}")

def format_duration(seconds) -> str:
    """초를 시간:분:초 형식으로 변환"""
    if not seconds:
        return "알 수 없음"
    
    seconds = int(float(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

# 스크립트를 문장 단위로 분할
def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할 (문장 종료 기호 기준)"""
    paragraphs = text.split('\n')
    
    result = []
    for para in paragraphs:
        if not para.strip():
            continue
        
        sentences = re.split(r'([.!?]+\s+)', para)
        
        current = ""
        for part in sentences:
            if not part:
                continue
            current += part
            if re.search(r'[.!?]+\s*$', current):
                if current.strip():
                    result.append(current.strip())
                    current = ""
        
        if current.strip():
            result.append(current.strip())
    
    return result if result else [text]

# PDF 생성 함수
def create_pdf_from_text(text: str, title: str, translated_text: Optional[str] = None) -> bytes:
    """텍스트를 PDF로 변환"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='black',
        spaceAfter=30,
        alignment=1
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        textColor='black'
    )
    
    story = []
    
    # 제목 추가
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # 원문 추가 (Original 제목 없이)
    # 텍스트를 문장 단위로 분할하여 PDF에 추가
    sentences = split_into_sentences(text)
    for sentence in sentences:
        if sentence.strip():
            sentence_escaped = sentence.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(sentence_escaped, body_style))
            story.append(Spacer(1, 0.1*inch))
    
    # 번역문이 있으면 추가
    if translated_text:
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("<b>번역 (Translation)</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        translated_sentences = split_into_sentences(translated_text)
        for sentence in translated_sentences:
            if sentence.strip():
                sentence_escaped = sentence.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(sentence_escaped, body_style))
                story.append(Spacer(1, 0.1*inch))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# Streamlit UI
def main():
    """Streamlit 메인 앱"""
    st.set_page_config(
        page_title="YouTube Script Auto",
        page_icon="🎬",
        layout="wide"
    )
    
    st.title("🎬 YouTube 스크립트 자동 추출")
    st.markdown("---")
    
    # 세션 상태 초기화
    if 'videos' not in st.session_state:
        st.session_state.videos = None
    if 'script_results' not in st.session_state:
        st.session_state.script_results = {}
    if 'audio_processes' not in st.session_state:
        st.session_state.audio_processes = {}
    if 'browser_audio' not in st.session_state:
        st.session_state.browser_audio = { 'playing': False, 'url': None }
    
    # 종료된 프로세스 정리
    if 'audio_processes' in st.session_state:
        for video_id, process in list(st.session_state.audio_processes.items()):
            if process and process.poll() is not None:
                # 프로세스가 이미 종료됨
                del st.session_state.audio_processes[video_id]
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        st.info("""
        **사용 방법:**
        1. 채널명 또는 채널 URL 입력
        2. 영상 목록 확인
        3. 스크립트 추출할 영상 선택
        4. 스크립트 다운로드
        """)
        st.markdown("---")
        st.caption("💡 **팁:** 채널 URL을 직접 입력하면 더 정확합니다")
        st.caption("예: `https://www.youtube.com/@channelname/videos`")
    
    # 채널 검색 섹션
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 세션 상태로 입력값 관리
        if 'channel_input_value' not in st.session_state:
            st.session_state.channel_input_value = ""
        if 'input_key' not in st.session_state:
            st.session_state.input_key = 0
        
        channel_input = st.text_input(
            "채널명 또는 채널 URL 입력",
            value=st.session_state.channel_input_value,
            placeholder="예: TED 또는 https://www.youtube.com/@TED/videos",
            key=f"channel_input_{st.session_state.input_key}"
        )
    
    with col2:
        st.write("")  # 간격 맞추기
        search_button = st.button("🔍 검색", type="primary", use_container_width=True)
    
    # 자주 쓰는 채널 빠른 선택 버튼 (URL 사용 - 더 빠름)
    st.markdown("### ⚡ 자주 쓰는 채널")
    quick_channel_epz = st.button("📻 English Podcast Zone", use_container_width=True)
    quick_channel_bob = st.button("📺 Learn English with Bob the Canadian", use_container_width=True)

    # 공통 핸들러
    def quick_search(channel_url: str, fallback_name: str):
        with st.spinner("채널을 검색하는 중..."):
            try:
                videos = _get_videos_from_url(channel_url, max_results=10)
                if not videos:
                    videos = get_channel_videos(fallback_name, max_results=10)
                if videos:
                    st.session_state.videos = videos
                    st.success(f"✅ {len(videos)}개의 영상을 찾았습니다!")
                    st.session_state.channel_input_value = ""
                    st.session_state.input_key += 1  # 입력창 key 변경으로 강제 재생성
                    st.rerun()
                else:
                    st.error("❌ 영상을 찾을 수 없습니다.")
                    st.session_state.videos = None
                    st.rerun()
            except Exception as e:
                st.error(f"오류 발생: {e}")
                st.session_state.videos = None

    # 빠른 선택 버튼 클릭 시 자동 검색 (URL 직접 사용으로 더 빠름)
    if quick_channel_epz:
        quick_search(
            channel_url="https://www.youtube.com/@EnglishPodcastZone/videos",
            fallback_name="English Podcast Zone",
        )
    if quick_channel_bob:
        quick_search(
            channel_url="https://www.youtube.com/@LearnEnglishwithBobtheCanadian/videos",
            fallback_name="Learn English with Bob the Canadian",
        )
    
    # 영상 검색 실행 (일반 검색 버튼)
    if search_button and channel_input:
        # 검색어 저장
        search_term = channel_input
        
        with st.spinner("채널을 검색하는 중..."):
            try:
                if search_term.startswith('http'):
                    videos = _get_videos_from_url(search_term, max_results=10)
                else:
                    videos = get_channel_videos(search_term, max_results=10)
                
                # 검색 완료 후 입력창 초기화
                st.session_state.channel_input_value = ""
                st.session_state.input_key += 1  # 입력창 key 변경으로 강제 재생성
                
                if videos:
                    st.session_state.videos = videos
                    st.success(f"✅ {len(videos)}개의 영상을 찾았습니다!")
                else:
                    st.error("❌ 영상을 찾을 수 없습니다. 채널명 또는 URL을 확인해주세요.")
                    st.session_state.videos = None
                
                # 페이지 재로드로 입력창 초기화 확실히 적용
                st.rerun()
            except Exception as e:
                # 오류 발생 시에도 입력창 초기화
                st.session_state.channel_input_value = ""
                st.session_state.input_key += 1
                st.error(f"오류 발생: {e}")
                st.session_state.videos = None
                st.rerun()
    
    # 영상 목록 표시
    if st.session_state.videos:
        st.markdown("---")
        st.subheader(f"📹 영상 목록 ({len(st.session_state.videos)}개)")
        
        videos_container = st.container()
        
        with videos_container:
            for video in st.session_state.videos:
                col1, col2, col3 = st.columns([1, 5, 1])
                
                with col1:
                    # 스크립트 추출 버튼
                    extract_key = f"extract_{video['id']}"
                    if st.button("📜 추출", key=extract_key, use_container_width=True):
                        safe_title = make_filesafe_title(video['title'])
                        script_text = get_youtube_script(video['url'], title=safe_title)
                        if script_text:
                            # 필요 시 번역을 메모리에서 수행
                            translated_text = None
                            if re.match(r'^[A-Za-z0-9\s.,!?\'"-]+$', script_text[:200]):
                                try:
                                    translator = GoogleTranslator(source='en', target='ko')
                                    translated_text = translator.translate(script_text)
                                except Exception:
                                    translated_text = None

                            st.session_state.script_results[video['id']] = {
                                'title': safe_title,
                                'script': script_text,
                                'translated': translated_text,
                                'url': video['url']
                            }
                            st.rerun()
                    
                    # 오디오 재생/정지 버튼 (브라우저 오디오 사용 - 창 닫히면 자동 종료)
                    video_id = video['id']
                    is_playing = st.session_state.browser_audio.get('playing', False) and \
                                 st.session_state.browser_audio.get('url') is not None and \
                                 st.session_state.browser_audio.get('video_id') == video_id

                    play_button_label = "⏸️ 정지" if is_playing else "🎧 재생"
                    audio_key = f"audio_{video['id']}"

                    if st.button(play_button_label, key=audio_key, use_container_width=True):
                        if is_playing:
                            # 정지: 브라우저 오디오 제거
                            st.session_state.browser_audio = { 'playing': False, 'url': None, 'video_id': None }
                        else:
                            try:
                                ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
                                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                    info = ydl.extract_info(video['url'], download=False)
                                    audio_url = info['url']
                                st.session_state.browser_audio = { 'playing': True, 'url': audio_url, 'video_id': video_id }
                            except Exception:
                                st.session_state.browser_audio = { 'playing': False, 'url': None, 'video_id': None }
                        st.rerun()

                    # 브라우저 오디오 렌더링 (컨트롤 숨김, 자동 재생)
                    if st.session_state.browser_audio.get('playing') and \
                       st.session_state.browser_audio.get('video_id') == video_id and \
                       st.session_state.browser_audio.get('url'):
                        components.html(
                            f"""
<audio src='{st.session_state.browser_audio['url']}' autoplay></audio>
""",
                            height=0,
                        )
                
                with col2:
                    duration_str = format_duration(video.get('duration', 0))
                    # 제목을 기본 폰트/기본 굵기로 보이도록 정규화하여 출력
                    title_norm = unicodedata.normalize('NFKD', video['title'])
                    title_norm = ''.join(c for c in title_norm if unicodedata.category(c) != 'Mn')
                    st.markdown(f"<div style='font-size: 20px; font-weight: 400; margin-bottom: 5px;'>{title_norm}</div>", unsafe_allow_html=True)
                    st.markdown(f"<p style='color: #666; margin-top: 5px;'>⏱️ {duration_str} | 🔗 <a href='{video['url']}' target='_blank'>YouTube 보기</a></p>", unsafe_allow_html=True)
                    
                    # 스크립트 결과가 있으면 표시
                    if video['id'] in st.session_state.script_results:
                        result = st.session_state.script_results[video['id']]
                        st.success(f"✅ 스크립트 추출 완료")
                        with st.expander("📜 스크립트 미리보기"):
                            # 문장 단위로 분할하여 표시
                            preview_text = result['script'][:2000] + ("..." if len(result['script']) > 2000 else "")
                            sentences = split_into_sentences(preview_text)
                            formatted_text = "\n\n".join(sentences)
                            st.text_area("", formatted_text, height=300, key=f"preview_{video['id']}")
                        
                        # 다운로드 버튼들 (원문과 PDF를 나란히 배치) - 메모리 데이터 사용
                        col_dl1, col_dl2, col_dl3 = st.columns([1, 1, 1])
                        
                        with col_dl1:
                            script_data = result.get('script') or ""
                            if script_data:
                                st.download_button(
                                    label="💾 원문 다운로드",
                                    data=script_data,
                                    file_name=f"{result['title']}_script.txt",
                                    mime="text/plain",
                                    key=f"dl_script_{video['id']}"
                                )
                        
                        with col_dl2:
                            # PDF 다운로드 (메모리 데이터 사용)
                            script_text = result.get('script') or ""
                            translated_text = result.get('translated')
                            if script_text:
                                display_title = result['title'].replace('_', ' ')
                                pdf_data = create_pdf_from_text(
                                    script_text,
                                    display_title,
                                    translated_text
                                )
                                pdf_filename = f"{display_title}.pdf"
                                st.download_button(
                                    label="📄 PDF 다운로드",
                                    data=pdf_data,
                                    file_name=pdf_filename,
                                    mime="application/pdf",
                                    key=f"dl_pdf_{video['id']}"
                                )
                        
                        with col_dl3:
                            translated_data = result.get('translated')
                            if translated_data:
                                st.download_button(
                                    label="🌐 번역 다운로드",
                                    data=translated_data,
                                    file_name=f"{result['title']}_translated.txt",
                                    mime="text/plain",
                                    key=f"dl_translated_{video['id']}"
                                )
                
                with col3:
                    video_num = video['index']
                    st.markdown(f"<div style='text-align: center; color: #888;'>#{video_num}</div>", unsafe_allow_html=True)
                
                st.markdown("---")

if __name__ == "__main__":
    main()
