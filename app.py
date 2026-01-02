import time
import csv
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def final_excel_crawl():
    # 1. 옵션 설정
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--incognito")  # 시크릿 모드 활성화
    
    # 2. 검색어부터 입력 받기 (터미널을 꼭 확인하세요!)
    print("\n" + "="*50)
    keyword = input(" [검색] 어떤 상품을 검색할까요? (입력 후 엔터): ").strip()
    print("="*50 + "\n")
    
    if not keyword:
        print("[오류] 검색어가 없습니다. 프로그램을 종료합니다.")
        return

    print(f"[실행] '{keyword}' 상품을 검색하기 위해 브라우저를 실행합니다...")
    
    # 3. 드라이버 실행
    driver = None
    try:
        print("[초기화] Chrome 드라이버를 초기화하는 중...")
        driver = uc.Chrome(options=options)
        print("[완료] 드라이버 초기화 완료!")
    except Exception as driver_error:
        print(f"[오류] 드라이버 초기화 실패: {driver_error}")
        print("\n[해결방법]")
        print("1. Chrome 브라우저를 완전히 종료한 후 다시 시도하세요")
        print("2. Chrome 브라우저를 최신 버전으로 업데이트하세요")
        return

    if driver is None:
        print("[오류] 드라이버가 초기화되지 않았습니다.")
        return

    try:
        # 4. URL 다이렉트 이동
        target_url = f"https://www.coupang.com/np/search?q={keyword}"
        print(f"[접속] 페이지 접속 중: {target_url}")
        driver.get(target_url)
        
        # 페이지 로딩을 위한 기본 대기
        time.sleep(5)
        
        # 스크롤을 통한 동적 콘텐츠 로딩 유도
        print("[대기] 페이지 로딩 및 스크롤 중...")
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # 5. 로딩 대기 - 여러 선택자 시도
        wait = WebDriverWait(driver, 20)
        print("[대기] 상품 리스트 로딩 대기 중...")
        
        # productList가 나타날 때까지 대기 (여러 방법 시도)
        product_list_found = False
        try:
            wait.until(EC.presence_of_element_located((By.ID, "productList")))
            print("[확인] productList 요소를 찾았습니다.")
            product_list_found = True
        except:
            pass
        
        if not product_list_found:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='ProductUnit']")))
                print("[확인] 상품 요소를 찾았습니다.")
            except:
                print("[경고] 상품 리스트 요소를 찾을 수 없지만 계속 진행합니다...")
                time.sleep(3)  # 추가 대기
        
        # 6. 상품 데이터 추출 - 여러 선택자 시도
        items = []
        selectors = [
            "ul#productList li",
            "li[class*='ProductUnit']",
            "li.search-product",
            "div[class*='ProductUnit']",
            "article[class*='product']",
            "li[class*='product']"
        ]
        
        for selector in selectors:
            try:
                items = driver.find_elements(By.CSS_SELECTOR, selector)
                if len(items) > 0:
                    print(f"[성공] 선택자 '{selector}'로 {len(items)}개의 요소를 찾았습니다.")
                    break
            except:
                continue
        
        data_list = []
        print(f"[수집] {len(items)}개의 상품 정보를 수집 중입니다...")
        
        if len(items) == 0:
            print("[오류] 상품을 찾을 수 없습니다. JavaScript로 DOM 탐색을 시도합니다...")
            try:
                # JavaScript로 상품 요소 찾기
                js_result = driver.execute_script("""
                    var products = document.querySelectorAll('li[class*="ProductUnit"], li.search-product, div[class*="ProductUnit"]');
                    return products.length;
                """)
                print(f"[디버그] JavaScript로 찾은 상품 수: {js_result}")
                
                if js_result > 0:
                    # JavaScript로 찾은 요소를 다시 Selenium으로 가져오기
                    items = driver.find_elements(By.CSS_SELECTOR, "li[class*='ProductUnit'], li.search-product, div[class*='ProductUnit']")
                    print(f"[성공] JavaScript를 통해 {len(items)}개의 상품을 찾았습니다.")
            except Exception as debug_error:
                print(f"[디버그] JavaScript 탐색 실패: {debug_error}")
                
            if len(items) == 0:
                print("[시도] 모든 li 요소를 확인합니다...")
                all_li = driver.find_elements(By.TAG_NAME, "li")
                print(f"[정보] 페이지에서 발견된 모든 li 요소 수: {len(all_li)}")
                
                # li 요소 중 상품명 클래스를 가진 것 찾기
                for li in all_li[:20]:  # 처음 20개만 확인
                    try:
                        if li.find_elements(By.CSS_SELECTOR, "[class*='ProductUnit'], [class*='productName'], [class*='Product']"):
                            items.append(li)
                            if len(items) >= 5:  # 5개 찾으면 충분
                                break
                    except:
                        continue
                
                if len(items) > 0:
                    print(f"[성공] {len(items)}개의 상품 요소를 찾았습니다.")
                
            if len(items) == 0:
                print("[오류] 모든 방법으로 상품을 찾을 수 없습니다.")
                print("[정보] 브라우저 창을 확인해보세요. 페이지가 정상적으로 로드되었는지 확인하세요.")
                print("[디버그] 브라우저를 10초 동안 열어둡니다. F12를 눌러 개발자 도구로 페이지 구조를 확인하세요.")
                time.sleep(10)
        else:
            # 랭킹 상품만 추출 (1위~10위)
            ranked_items = []
            for item in items:
                try:
                    # 랭킹 추출
                    rank = None
                    try:
                        rank_elem = item.find_element(By.CSS_SELECTOR, "[class*='RankMark']")
                        rank_text = rank_elem.text.strip()
                        # 숫자만 추출
                        rank_match = re.search(r'(\d+)', rank_text)
                        if rank_match:
                            rank = int(rank_match.group(1))
                            # 1위부터 10위까지만
                            if 1 <= rank <= 10:
                                ranked_items.append((rank, item))
                    except:
                        # 랭킹이 없는 상품은 제외
                        continue
                except:
                    continue
            
            # 랭킹 순서로 정렬
            ranked_items.sort(key=lambda x: x[0])
            print(f"[랭킹] {len(ranked_items)}개의 랭킹 상품(1~10위)을 찾았습니다.")
            
            for rank, item in ranked_items:
                try:
                    # 상품명 추출
                    name_elem = item.find_element(By.CSS_SELECTOR, ".ProductUnit_productNameV2__cV9cw")
                    name = name_elem.text.strip()
                    
                    # 리뷰수 추출
                    review_count = ""
                    try:
                        # 콤마 포함 리뷰수도 안전하게 추출 (예: "(3,050)" -> "3,050")
                        review_container = item.find_element(By.CSS_SELECTOR, ".ProductRating_productRating__jjf7W")
                        review_text = (review_container.text or review_container.get_attribute("textContent") or "").strip()

                        match = re.search(r'\(([^)]*)\)', review_text)
                        if match:
                            inside = match.group(1).strip()
                            cleaned = re.sub(r'[^0-9,]', '', inside)
                            review_count = cleaned if re.search(r'\d', cleaned) else "리뷰 없음"
                        else:
                            review_count = "리뷰 없음"
                    except:
                        review_count = "리뷰 없음"
                    
                    if name:  # 상품명이 있는 경우만 추가
                        data_list.append([rank, name, review_count])
                except Exception as e:
                    continue

        # 7. 엑셀(CSV) 파일 저장
        file_name = f"쿠팡_{keyword}_랭킹결과.csv"
        with open(file_name, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["랭킹", "상품명", "리뷰수"]) # 제목 행
            writer.writerows(data_list)
        
        print(f"\n[완료] 저장 완료: {file_name}")
        print(f"[파일] 현재 폴더에서 '{file_name}' 파일을 확인하세요!")

    except Exception as e:
        print(f"[오류] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 드라이버 안전하게 종료
        if driver:
            print("\n[종료] 브라우저를 종료하는 중...")
            try:
                driver.quit()
            except:
                try:
                    driver.close()
                except:
                    pass

if __name__ == "__main__":
    final_excel_crawl()
