CSS = '''<style>
:root{--navy:#122236;--mint:#10b990;--line:#e5ecf5}
.stApp{background:linear-gradient(115deg,#f8fbff,#fff)}
.block-container{padding-top:1.3rem;max-width:1800px}
[data-testid="stSidebar"]{background:linear-gradient(160deg,#14283e,#0d1c2e);min-width:210px;max-width:250px}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#e7f0ff}
[data-testid="stSidebar"] [data-testid="stExpander"]{background:#1b334b}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);padding:16px;border-radius:15px;box-shadow:0 5px 20px #14283e05}
[data-testid="stMetricLabel"]{color:#52708a;font-size:13px}
[data-testid="stMetricValue"]{color:#122236;font-size:26px}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:16px;border-color:var(--line);box-shadow:0 4px 18px #14283e04}
[data-testid="stExpander"]{background:#fff;border-radius:12px}
h1{font-size:28px!important} h2{font-size:21px!important} h3{font-size:17px!important}
.stButton>button{border-radius:10px}.stButton>button[kind="primary"]{background:#09ae86;border:0}
.brand{color:#fff;font-weight:750;font-size:21px}.brand-sub{color:#a8bfd8;font-size:12px;margin-bottom:22px}
.topbar{display:flex;justify-content:space-between;padding:10px 0 18px;border-bottom:1px solid var(--line);margin-bottom:18px;gap:12px;flex-wrap:wrap}
.topbar b{color:#132844;font-size:22px}.topbar span{color:#72829a;font-size:12px}
.pill{display:inline-block;padding:5px 10px;border-radius:30px;background:#e6fbf3;color:#008964;font-size:12px}
.client-title{font-size:22px;font-weight:750;color:#152642;margin:12px 0}
.ai-box{background:linear-gradient(135deg,#f3f0ff,#f7faff);border:1px solid #dcd5ff;border-radius:12px;padding:16px;color:#343066}
.muted{color:#7c8da3;font-size:12px}
[data-testid="stTabs"] [data-baseweb="tab"]{font-size:13px}
@media(max-width:900px){.block-container{padding:1rem}.topbar b{font-size:18px}[data-testid="stMetricValue"]{font-size:20px}}
</style>'''
