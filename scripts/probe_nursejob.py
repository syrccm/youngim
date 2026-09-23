"""널스잡 접근성 확인용 (1회성). 결과를 data/debug/probe.txt 에 기록."""
import urllib.request, pathlib, socket, time, subprocess
out=pathlib.Path(__file__).resolve().parent.parent/"data"/"debug"; out.mkdir(parents=True,exist_ok=True)
log=[]
def w(*a):
    s=" ".join(str(x) for x in a); print(s); log.append(s)
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36","Accept-Language":"ko-KR,ko;q=0.9","Accept":"text/html"}
for host in ["www.nursejob.co.kr","nursejob.co.kr"]:
    try: w(host,"->",socket.gethostbyname(host))
    except Exception as e: w(host,"DNS ERR",e)
for u in ["https://www.nursejob.co.kr/","http://www.nursejob.co.kr/","https://www.nursejob.co.kr/recruit/list.php?m=jikjong&w_jik%5B%5D=1006&num=1"]:
    t=time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=25) as r:
            b=r.read(); w(u,r.status,len(b),round(time.time()-t,1),"s"); (out/("page%d.html"%len(log))).write_bytes(b)
    except Exception as e:
        w(u,"ERR",repr(e),round(time.time()-t,1),"s")
try:
    w(subprocess.run(["curl","-sS","-m","25","-o","/dev/null","-w","%{http_code} %{time_total}","-A",H["User-Agent"],"https://www.nursejob.co.kr/"],capture_output=True,text=True).stdout)
except Exception as e: w("curl ERR",e)
(out/"probe.txt").write_text("\n".join(log),encoding="utf-8")
