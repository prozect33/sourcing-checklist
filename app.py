import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# Supabase 연결 설정 (실제 환경에서는 환경 변수를 사용하세요)
# st.secrets를 사용하여 Supabase 연결 정보를 가져옵니다.
try:
    url: str = st.secrets["supabase_url"]
    key: str = st.secrets["supabase_key"]
    supabase: Client = create_client(url, key)
except KeyError:
    st.error("Supabase 연결 정보(URL, Key)가 st.secrets에 설정되지 않았습니다. 연결 설정을 확인해주세요.")
    # 임시/더미 클라이언트 생성 (실제 동작은 안 함)
    class DummyClient:
        def table(self, table_name): return self
        def insert(self, data): return self
        def select(self, columns): return self
        def execute(self): return self
        def update(self, data): return self
        def eq(self, column, value): return self
        def order(self, column): return self
        def delete(self): return self
    supabase = DummyClient()


# 탭 1: 상품 등록 및 조회
def tab1_content():
    st.header("🛒 상품 정보 관리")

    with st.expander("상품 등록"):
        with st.form("product_form"):
            st.markdown("#### 기본 정보")
            product_name = st.text_input("상품 이름", key="p_name")
            sell_price = st.number_input("판매가 (부가세 포함)", min_value=0, step=100, key="p_sell_price")
            fee = st.number_input("수수료율 (%)", min_value=0.0, max_value=100.0, step=0.1, key="p_fee")
            quantity = st.number_input("재고 수량", min_value=0, step=1, key="p_quantity")

            st.markdown("#### 매입 및 원가 정보 (총액 기준)")
            purchase_cost = st.number_input("매입비 총액", min_value=0, step=1000, key="p_purchase_cost")
            logistics_cost = st.number_input("총 물류비", min_value=0, step=100, key="p_logistics_cost")
            customs_duty = st.number_input("총 관세", min_value=0, step=100, key="p_customs_duty")
            etc_cost = st.number_input("총 기타 비용", min_value=0, step=100, key="p_etc_cost")

            st.markdown("#### 개별 발송 비용 (건당/단위 비용)")
            inout_shipping_cost = st.number_input("입출고/배송비 (건당)", min_value=0, step=100, key="p_inout_shipping_cost")
            
            submitted = st.form_submit_button("상품 등록/수정")

            if submitted:
                if product_name and sell_price > 0 and quantity >= 0:
                    # 단위 원가 계산 (수량이 0이면 1로 나누어 UnboundError 방지)
                    qty_for_calc = quantity if quantity > 0 else 1
                    unit_purchase_cost = round(purchase_cost / qty_for_calc)
                    unit_logistics_cost = round(logistics_cost / qty_for_calc)
                    unit_customs_duty = round(customs_duty / qty_for_calc)
                    unit_etc_cost = round(etc_cost / qty_for_calc)

                    product_data = {
                        "product_name": product_name,
                        "sell_price": sell_price,
                        "fee": fee,
                        "quantity": quantity,
                        "purchase_cost": purchase_cost,
                        "logistics_cost": logistics_cost,
                        "customs_duty": customs_duty,
                        "etc_cost": etc_cost,
                        "inout_shipping_cost": inout_shipping_cost,
                        "unit_purchase_cost": unit_purchase_cost,
                        "unit_logistics_cost": unit_logistics_cost,
                        "unit_customs_duty": unit_customs_duty,
                        "unit_etc_cost": unit_etc_cost,
                    }

                    try:
                        # 이미 존재하는 상품인지 확인
                        response = supabase.table("products").select("product_name").eq("product_name", product_name).execute()
                        
                        if response.data:
                            # 기존 상품 수정
                            supabase.table("products").update(product_data).eq("product_name", product_name).execute()
                            st.success(f"상품 **{product_name}** 정보가 수정되었습니다.")
                        else:
                            # 새 상품 등록
                            supabase.table("products").insert(product_data).execute()
                            st.success(f"새 상품 **{product_name}**이 등록되었습니다.")
                    except Exception as e:
                        st.error(f"상품 등록/수정 중 오류가 발생했습니다: {e}")
                else:
                    st.error("상품 이름, 판매가, 수량은 필수 입력 항목입니다.")

    st.markdown("---")
    st.subheader("📚 등록된 상품 목록")
    
    try:
        response = supabase.table("products").select("*").order("product_name").execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            df = df.rename(columns={
                "product_name": "상품 이름",
                "sell_price": "판매가",
                "fee": "수수료율(%)",
                "quantity": "재고 수량",
                "purchase_cost": "매입비 총액",
                "logistics_cost": "총 물류비",
                "customs_duty": "총 관세",
                "etc_cost": "총 기타 비용",
                "inout_shipping_cost": "건당 배송비",
                "unit_purchase_cost": "단위 매입단가",
                "unit_logistics_cost": "단위 물류비",
                "unit_customs_duty": "단위 관세",
                "unit_etc_cost": "단위 기타비용",
            })
            
            # 보기 편하게 일부 컬럼만 선택하고 포맷팅
            display_cols = [
                "상품 이름", "판매가", "수수료율(%)", "재고 수량", 
                "단위 매입단가", "건당 배송비", "단위 물류비", 
                "단위 관세", "단위 기타비용"
            ]
            
            df_display = df[display_cols].copy()
            
            for col in ["판매가", "단위 매입단가", "건당 배송비", "단위 물류비", "단위 관세", "단위 기타비용"]:
                df_display[col] = df_display[col].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(df_display, use_container_width=True)

            # 상품 삭제 기능
            st.markdown("---")
            st.subheader("상품 삭제")
            product_names = df["상품 이름"].tolist()
            product_to_delete = st.selectbox("삭제할 상품 선택", ["선택하세요"] + product_names, key="delete_select")
            
            if product_to_delete != "선택하세요":
                if st.button(f"'{product_to_delete}' 상품 삭제", key="delete_button"):
                    try:
                        supabase.table("products").delete().eq("product_name", product_to_delete).execute()
                        st.success(f"상품 **{product_to_delete}**가 삭제되었습니다.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"상품 삭제 중 오류가 발생했습니다: {e}")

        else:
            st.info("등록된 상품이 없습니다.")
            
    except Exception as e:
        st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

# 탭 2: 일일 정산 (사용자 요청 로직 반영)
def tab2_content():
    st.header("📈 일일 정산 계산 및 저장")

    with st.expander("일일 정산"):
        product_list = ["상품을 선택해주세요"]
        try:
            response = supabase.table("products").select("product_name").order("product_name").execute()
            if response.data:
                saved_products = [item['product_name'] for item in response.data]
                product_list.extend(saved_products)
        except Exception as e:
            st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

        selected_product_name = st.selectbox("상품 선택", product_list, key="product_select_daily")

        product_data = {}
        if selected_product_name and selected_product_name != "상품을 선택해주세요":
            try:
                response = supabase.table("products").select("*").eq("product_name", selected_product_name).execute()
                if response.data:
                    product_data = response.data[0]
            except Exception as e:
                st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

        with st.expander("상품 상세 정보"):
            if selected_product_name == "상품을 선택해주세요":
                st.info("먼저 상품을 선택해주세요.")
            elif product_data:
                # 단위 원가 정보는 이미 tab1에서 계산되어 저장됨
                st.markdown(f"**판매가:** {product_data.get('sell_price', 0):,}원")
                st.markdown(f"**수수료율:** {product_data.get('fee', 0.0):.2f}%")
                st.markdown(f"**건당 입출고/배송비:** {product_data.get('inout_shipping_cost', 0):,}원")
                st.markdown(f"**단위 매입단가:** {product_data.get('unit_purchase_cost', 0):,.0f}원")
                st.markdown(f"**단위 물류비:** {product_data.get('unit_logistics_cost', 0):,.0f}원")
                st.markdown(f"**단위 관세:** {product_data.get('unit_customs_duty', 0):,.0f}원")
                st.markdown(f"**단위 기타 비용:** {product_data.get('unit_etc_cost', 0):,.0f}원")
            else:
                st.info("선택된 상품의 상세 정보가 없습니다.")

        report_date = st.date_input("날짜 선택", datetime.date.today())

        st.markdown("---")
        st.markdown("#### 판매 현황 입력")
        total_sales_qty = st.number_input("전체 판매 수량", min_value=0, step=1, key="total_sales_qty")
        total_revenue = st.number_input("전체 매출액", min_value=0, step=1000, key="total_revenue")

        st.markdown("---")
        st.markdown("#### 광고 비용 입력")
        ad_cost = st.number_input("총 광고비", min_value=0, step=1000, key="ad_cost")
        
        # 광고/자연 판매는 계산에 직접 쓰이지 않지만 현황 파악을 위해 입력받음
        st.markdown("---")
        st.markdown("#### 광고/자연 판매 (선택 사항)")
        ad_sales_qty = st.number_input("광고 전환 판매 수량", min_value=0, step=1, key="ad_sales_qty")
        ad_revenue = st.number_input("광고 전환 매출액", min_value=0, step=1000, key="ad_revenue")

        # 🔹 자동 계산
        organic_sales_qty_calc = max(total_sales_qty - ad_sales_qty, 0)
        organic_revenue_calc = max(total_revenue - ad_revenue, 0)

        # UI 그대로 유지, disabled
        st.number_input(
            "자연 판매 수량",
            value=organic_sales_qty_calc,
            disabled=True,
            key="organic_sales_qty_display"
        )
        st.number_input(
            "자연 판매 매출액",
            value=organic_revenue_calc,
            disabled=True,
            key="organic_revenue_display"
        )


        st.markdown("---")
        st.subheader("💰 일일 순이익 계산 결과")

        # 💡 UnboundLocalError 방지를 위해 초기화
        daily_profit = 0
        
        if selected_product_name != "상품을 선택해주세요" and product_data:
            # 1. 상품 상세 정보 불러오기 (단위 원가는 이미 tab1에서 계산되어 저장된 값 사용)
            fee_rate_val = product_data.get("fee", 0.0)
            inout_shipping_cost_unit = product_data.get("inout_shipping_cost", 0) # 건당 배송비 (단가)
            
            unit_purchase_cost = product_data.get("unit_purchase_cost", 0)
            unit_logistics = product_data.get("unit_logistics_cost", 0)
            unit_customs = product_data.get("unit_customs_duty", 0)
            unit_etc = product_data.get("unit_etc_cost", 0)
            
            ad_cost_total = ad_cost  # 사용자가 입력한 총 광고비

            # 2. 사용자님이 제시한 로직을 적용하여 일일 순이익금 계산
            
            # 가. 전체 매출액
            revenue_total = total_revenue
            
            # 나. 총 비용 항목 계산
            
            # (1) 수수료 총액: (전체 매출액 * 수수료율 / 100 * 1.1 VAT)
            fee_total = revenue_total * fee_rate_val / 100 * 1.1
            
            # (2) 매입 원가 총액: (단위 매입단가 * 전체 판매 수량)
            purchase_total = unit_purchase_cost * total_sales_qty
            
            # (3) 입출고/배송비 총액: (건당 배송비 * 전체 판매 수량 * 1.1 VAT)
            inout_shipping_total = inout_shipping_cost_unit * total_sales_qty * 1.1
            
            # (4) 물류비/관세/기타 총액: (단위 비용 * 전체 판매 수량)
            logistics_total = unit_logistics * total_sales_qty
            customs_total = unit_customs * total_sales_qty
            etc_total = unit_etc * total_sales_qty
            
            # (5) 광고비 총액: (총 광고비 * 1.1 VAT)
            ad_cost_with_vat = ad_cost_total * 1.1
            
            # 4. 최종 일일 순이익금 계산: 총 매출액 - 모든 총 비용 합계
            daily_profit = (
                revenue_total 
                - fee_total
                - purchase_total
                - inout_shipping_total
                - logistics_total
                - customs_total
                - etc_total
                - ad_cost_with_vat
            )
            
            daily_profit = round(daily_profit) # 정수 변환

        # 💡 계산 결과 표시
        st.metric(label="일일 순이익금", value=f"{int(daily_profit):,}원")

        # 💡 저장 버튼
        if st.button("일일 정산 저장하기"):
            if selected_product_name == "상품을 선택해주세요" or total_sales_qty == 0:
                st.error("상품을 선택하고 판매 수량을 1개 이상 입력해야 저장할 수 있습니다.")
            else:
                try:
                    daily_report_data = {
                        "date": report_date.isoformat(),
                        "product_name": selected_product_name,
                        "total_sales_qty": total_sales_qty,
                        "total_revenue": total_revenue,
                        "ad_sales_qty": ad_sales_qty,
                        "ad_revenue": ad_revenue,
                        "ad_cost": ad_cost,
                        "organic_sales_qty": organic_sales_qty_calc,
                        "organic_revenue": organic_revenue_calc,
                        "calculated_profit": daily_profit,
                        # 계산에 사용된 비용 항목도 저장 (투명성 확보)
                        "fee_total": round(fee_total),
                        "purchase_total": round(purchase_total),
                        "inout_shipping_total": round(inout_shipping_total),
                        "logistics_total": round(logistics_total),
                        "customs_total": round(customs_total),
                        "etc_total": round(etc_total),
                        "ad_cost_with_vat": round(ad_cost_with_vat),
                    }
                    
                    # 기존 데이터가 있으면 업데이트, 없으면 삽입 (날짜 + 상품명 기준)
                    response = supabase.table("daily_reports").select("*").eq("date", report_date.isoformat()).eq("product_name", selected_product_name).execute()

                    if response.data:
                         # 업데이트
                        supabase.table("daily_reports").update(daily_report_data).eq("date", report_date.isoformat()).eq("product_name", selected_product_name).execute()
                        st.success(f"**{report_date.isoformat()}** 날짜의 **{selected_product_name}** 정산 기록이 수정되었습니다.")
                    else:
                        # 삽입
                        supabase.table("daily_reports").insert(daily_report_data).execute()
                        st.success(f"**{report_date.isoformat()}** 날짜의 **{selected_product_name}** 정산 기록이 저장되었습니다.")

                except Exception as e:
                    st.error(f"정산 기록 저장 중 오류가 발생했습니다: {e}")


    st.markdown("---")
    st.subheader("📊 정산 기록 조회")
    
    try:
        response = supabase.table("daily_reports").select("*").order("date", desc=True).order("product_name").execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            df = df.rename(columns={
                "date": "날짜",
                "product_name": "상품 이름",
                "total_sales_qty": "총 수량",
                "total_revenue": "총 매출액",
                "calculated_profit": "순이익",
                "ad_cost": "총 광고비(VAT제외)",
                "ad_sales_qty": "광고 수량",
                "ad_revenue": "광고 매출",
                "organic_sales_qty": "자연 수량",
                "organic_revenue": "자연 매출",
            })
            
            # 보기 편하게 일부 컬럼만 선택하고 포맷팅
            display_cols = [
                "날짜", "상품 이름", "총 수량", "총 매출액", "순이익", 
                "총 광고비(VAT제외)", "광고 수량", "광고 매출", "자연 수량", "자연 매출"
            ]
            
            df_display = df[display_cols].copy()
            
            # 금액 관련 컬럼 포맷팅
            for col in ["총 매출액", "순이익", "총 광고비(VAT제외)", "광고 매출", "자연 매출"]:
                df_display[col] = df_display[col].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(df_display, use_container_width=True)

        else:
            st.info("저장된 정산 기록이 없습니다.")
            
    except Exception as e:
        st.error(f"정산 기록을 불러오는 중 오류가 발생했습니다: {e}")


# 메인 함수
def main():
    st.set_page_config(layout="wide", page_title="재고/정산 관리 시스템")

    st.title("재고/정산 관리 시스템 💰")

    tab1, tab2 = st.tabs(["상품 정보 관리", "일일 정산"])

    with tab1:
        tab1_content()

    with tab2:
        tab2_content()

if __name__ == "__main__":
    main()
