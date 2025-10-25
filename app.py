import streamlit as st

# 🚨 초기값 설정: 리셋되었을 때 보여줄 가시적인 기본값
INITIAL_ITEM_NAME = "--- 새 상품 이름을 입력해주세요 (필수) ---"
INITIAL_PRICE = 10000

st.title("상품 입력 모드 리셋 테스트 (최종 해결)")
st.info("✅ 저장 버튼 클릭 시 모든 필드가 초기값으로 자동 리셋됩니다.")

# 1. '저장하기' 기능을 st.form으로 구현
# clear_on_submit=True 설정이 핵심입니다!
with st.form(key="new_product_form", clear_on_submit=True):
    st.header("💾 새로운 상품 등록")

    # 입력 필드 (초기값 설정)
    product_name = st.text_input(
        "상품 이름",
        value=INITIAL_ITEM_NAME, # 폼이 리셋될 때 이 값으로 돌아갑니다.
        key="form_name_input"
    )

    product_price = st.number_input(
        "가격",
        min_value=0,
        value=INITIAL_PRICE, # 폼이 리셋될 때 이 값으로 돌아갑니다.
        key="form_price_input"
    )

    # 폼 제출 버튼
    submitted = st.form_submit_button("저장하기")

    if submitted:
        # 여기에 저장 로직을 넣습니다. (예: DB에 데이터 삽입)
        if product_name == INITIAL_ITEM_NAME or product_name.strip() == "":
            st.error("상품 이름을 입력해주세요.")
        else:
            st.success(f"상품 '{product_name}'이(가) 저장되었습니다. (필드 자동 리셋 완료)")
            # 폼 제출 후 clear_on_submit=True에 의해 모든 입력 필드가 INITIAL_VALUE로 리셋됨


# 2. '수정/삭제' 후 '새 상품 입력 모드'로 전환하는 함수
# 이 기능은 st.form 밖의 일반 버튼에 필요합니다.
def reset_for_edit_delete():
    """수정/삭제 후 입력 필드를 비우고 새 모드로 전환"""
    
    # st.session_state를 사용하여 폼 필드 키의 값을 명시적으로 초기화합니다.
    # st.session_state['[form_key]-[widget_key]'] 패턴으로 접근해야 합니다.
    # st.session_state['new_product_form-form_name_input'] = INITIAL_ITEM_NAME # Streamlit 버전 및 설정에 따라 이 패턴이 필요할 수 있습니다.
    
    # st.rerun()을 사용하여 전체 앱을 재실행합니다.
    # 이렇게 하면 폼 자체가 처음부터 다시 그려지며 리셋됩니다.
    st.session_state['reset_flag'] = True
    st.experimental_rerun()


if 'reset_flag' in st.session_state and st.session_state['reset_flag']:
    del st.session_state['reset_flag'] # 플래그 제거
    # st.success("수정/삭제 후 새로운 입력 모드로 돌아왔습니다.") # 필요시 메시지 표시

st.markdown("---")
st.header("✏️ 기존 상품 관리 (수동 리셋 필요)")

col1, col2 = st.columns(2)

with col1:
    if st.button("✏️ 수정하기", use_container_width=True, on_click=reset_for_edit_delete):
        # 수정 로직 실행
        st.warning("수정 완료! 새로운 상품 입력 모드로 돌아갑니다.")

with col2:
    if st.button("🗑️ 삭제하기", use_container_width=True, on_click=reset_for_edit_delete):
        # 삭제 로직 실행
        st.error("삭제 완료! 새로운 상품 입력 모드로 돌아갑니다.")
