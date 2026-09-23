"""널스잡 페이지 구조 확인용 (1회성). 검색 목록 HTML을 data/debug/ 에 저장."""
import urllib.request, urllib.parse, pathlib, sys
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36","Accept-Language":"ko-KR,ko;q=0.9"}
out=pathlib.Path(__file__).resolve().parent.parent/"data"/"debug"; out.mkdir(parents=True,exist_ok=True)
urls={
 "list_jikjong.html":"https://www.nursejob.co.kr/recruit/list.php?m=jikjong&w_jik%5B%5D=1006&num=1",
 "list_search.html":"https://www.nursejob.co.kr/recruit/list.php?m=jikjong&w_jik%5B%5D=1006&w_jik%5B%5D=1007&num=1&sido=%EB%B6%80%EC%82%B0",
 "search_kw.html":"https://www.nursejob.co.kr/recruit/list.php?m=search&keyword=%EC%88%98%EA%B0%84%ED%98%B8%EC%82%AC",
}
for name,u in urls.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60) as r:
            b=r.read(); (out/name).write_bytes(b); print(name,len(b),r.status,r.headers.get("content-type"))
    except Exception as e:
        print(name,"ERR",e)
