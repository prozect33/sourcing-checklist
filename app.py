import streamlit as st

# 🚨 초기값 설정
INITIAL_ITEM_NAME = "상품 이름을 여기에 입력하세요"
INITIAL_PRICE = 10000

# 1. 세션 상태 초기화 블록 (반드시 모든 키를 여기서 정의해야 합니다)
# 'item_name'이나 'item_price' 중 하나라도 없으면 모두 초기화합니다.
if 'item_name' not in st.session_state or 'item_price' not in st.session_state:
    st.session_state.item_name = INITIAL_ITEM_NAME
    st.session_state.item_price = INITIAL_PRICE
    # 상태 메시지 초기화
    if 'status' not in st.session_state:
        st.session_state.status = "➡️ 현재: 새로운 상품 입력 모드"


# 2. 콜백 함수 정의: 필드 값을 초기값으로 리셋 및 상태 변경
def reset_mode_and_field():
    """버튼 클릭 시 실행되어 입력 상태와 필드 값을 '가시적인 초기값'으로 리셋"""
    
    # 세션 상태 값을 INITIAL_VALUE로 초기화
    st.session_state.item_name = INITIAL_ITEM_NAME
    st.session_state.item_price = INITIAL_PRICE
    
    # 상태 메시지 변경
    st.session_state.status = "✅ 리셋 성공! 새로운 상품 입력 모드로 전환됨"
    

# 3. UI 구성
st.title("상품 입력 모드 리셋 테스트 (수정됨)")
st.info(st.session_state.status) # 초기화가 보장된 status 사용

# --- 입력 필드 ---

# 상품 이름 (텍스트 입력)
# 'value' 파라미터가 초기화된 세션 상태 변수에 안전하게 접근합니다.
product_name = st.text_input(
    "상품 이름",
    value=st.session_state.item_name,
    key='product_name_input'
)

# 가격 (숫자 입력)
# 'value' 파라미터가 초기화된 세션 상태 변수에 안전하게 접근합니다.
product_price = st.number_input(
    "가격",
    min_value=0,
    value=st.session_state.item_price,
    key='product_price_input'
)

# 4. 테스트 버튼
if st.button("💾 저장하기 (리셋 테스트)", on_click=reset_mode_and_field):
    st.success(f"상품 '{product_name}'이(가) 저장되었습니다. 이제 필드가 초기값으로 돌아갑니다.")
