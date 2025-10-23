# ... (중략)

# 상품 정보 불러오기/리셋 함수
def load_product_data(selected_product_name):
    # ... (중략)
    # 기존 코드 유지: "새로운 상품 입력" 선택 시 모든 필드를 빈 상태로 초기화
    # ... (중략)

# 메인 함수
def main():
    
    # ... (중략)
    
    with tab2:
        st.subheader("세부 마진 계산기")
    
        with st.expander("상품 정보 입력"):
            # ... (중략) 상품 목록 로딩 및 선택 코드 유지
            
            # ... (중략) 입력 필드 정의 코드 유지
            
            
            if st.session_state.is_edit_mode:
                
                col_mod, col_del = st.columns(2)
                
                # 1. 수정하기 버튼
                with col_mod:
                    if st.button("수정하기"):
                        try:
                            data_to_update = {
                                "sell_price": sell_price,
                                "fee": fee_rate,
                                # ... (나머지 필드)
                                "etc_cost": etc_cost,
                            }
                            supabase.table("products").update(data_to_update).eq("product_name", st.session_state.product_name_edit).execute()
                            
                            # ✨ 수정된 부분: 성공 문구 제거
                            
                            # 🚨 중요: 새로고침 시 모든 입력 필드를 빈 상태로 만들기 위해 상태 초기화
                            st.session_state.is_edit_mode = False
                            st.session_state.product_name_edit = ""
                            st.session_state.confirm_delete = False
                            st.session_state.product_loader = "새로운 상품 입력" # 드롭다운 초기화
                            
                            st.rerun() 
                            
                        except Exception as e:
                            st.error(f"데이터 수정 중 오류가 발생했습니다: {e}")

                # 2. 삭제하기 버튼 (1차 클릭)
                with col_del:
                    if st.button("삭제하기", key="delete_button_main"):
                        st.session_state.confirm_delete = True
                
                # 3. 삭제 확인 UI (2차 클릭)
                if st.session_state.confirm_delete:
                    st.warning(f"⚠️ **'{st.session_state.product_name_edit}'** 상품을 정말로 삭제하시겠습니까?")
                    
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        # 최종 확인 버튼
                        if st.button("✅ 네, 삭제합니다", key="delete_confirm"):
                            try:
                                deleted_name = st.session_state.product_name_edit
                                supabase.table("products").delete().eq("product_name", deleted_name).execute()
                                
                                # 🚨 중요: 새로고침 시 모든 입력 필드를 빈 상태로 만들기 위해 상태 초기화
                                st.session_state.is_edit_mode = False
                                st.session_state.product_name_edit = ""
                                st.session_state.confirm_delete = False
                                st.session_state.product_loader = "새로운 상품 입력" # 드롭다운 초기화
                                
                                # ✨ 수정된 부분: 성공 문구 제거
                                st.rerun() 
                                
                            except Exception as e:
                                st.error(f"데이터 삭제 중 오류가 발생했습니다: {e}")
                                st.session_state.confirm_delete = False
                        
                    with col_cancel:
                        # 취소 버튼
                        if st.button("❌ 취소합니다", key="delete_cancel"):
                            st.session_state.confirm_delete = False
            
            else: # is_edit_mode가 False일 때 (신규 상품 입력)
                if st.button("상품 저장하기"):
                    if not product_name or sell_price == 0:
                        st.warning("상품명과 판매가를 입력해 주세요.")
                    else:
                        try:
                            # ... (데이터 저장 로직 유지)
                            
                            # ✨ 수정된 부분: 성공 문구 제거
                            
                            # 🚨 중요: 새로고침 시 모든 입력 필드를 빈 상태로 만들기 위해 상태 초기화
                            st.session_state.is_edit_mode = False
                            st.session_state.product_name_edit = ""
                            st.session_state.confirm_delete = False
                            st.session_state.product_loader = "새로운 상품 입력" # 드롭다운 초기화
                            
                            st.rerun() 
                            
                        except Exception as e:
                            st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

# ... (중략)
