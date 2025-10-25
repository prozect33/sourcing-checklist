import streamlit as st

# 1. 세션 상태 초기화
# 'item_name'은 입력 필드의 값을 저장하고, 'status'는 현재 모드를 표시합니다.
if 'item_name' not in st.session_state:
    st.session_state.item_name = ""
    st.session_state.status = "➡️ 현재: 새로운 상품 입력 모드"

# 2. 콜백 함수 정의: 필드 값을 초기화하고 상태를 변경
def reset_mode_and_field():
    """버튼 클릭 시 실행되어 입력 상태와 필드 값을 리셋"""
    
    # 1. 입력 필드의 세션 상태 값을 초기화 (가장 중요)
    st.session_state.item_name = "" 
    
    # 2. 상태 메시지 변경 (리셋이 성공했음을 시각적으로 확인)
    st.session_state.status = "✅ 리셋 성공! 새로운 상품 입력 모드로 전환됨"
    
    # 참고: 실제 저장/수정/삭제 로직은 이 함수 내 또는 버튼 클릭 조건문 내에 배치됩니다.


# 3. UI 구성
st.title("상품 입력 모드 리셋 테스트")
st.info(st.session_state.status) # 현재 상태 표시

# 입력 필드: 반드시 key를 사용해야 Session State로 값을 읽고 쓸 수 있습니다.
# **st.session_state.item_name**의 값을 **value**로 사용하여 값을 제어합니다.
product_name = st.text_input(
    "상품 이름",
    value=st.session_state.item_name,
    key='product_name_input' # 필수: 사용자가 입력 시 이 키로 세션 상태가 업데이트됨
)

# 4. 테스트 버튼
# on_click에 리셋 함수를 연결합니다.
if st.button("💾 저장하기 (리셋 테스트)", on_click=reset_mode_and_field):
    # 이 조건문 내부의 로직은 콜백 함수가 실행된 **후**에 실행됩니다.
    st.success(f"상품 '{product_name}' 저장 완료! 이제 필드가 리셋됩니다.")
