CSS = '''<style>
:root{--navy:#142336;--mint:#00b68a;--line:#e4eaf5;--text:#14223f;--muted:#7281a3}
.stApp{background:linear-gradient(115deg,#f7faff 0%,#fff 70%);color:var(--text)}
header[data-testid="stHeader"]{background:transparent!important;height:3rem}
.block-container{padding:4rem 1.3rem 2rem;max-width:1920px}
[data-testid="stMainBlockContainer"]>div>[data-testid="stVerticalBlock"]{gap:.8rem}
[data-testid="stSidebar"]{background:linear-gradient(155deg,#182b40,#101d2b);min-width:190px;max-width:215px;border-right:1px solid #25384d}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:.75rem}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#d8e7fa}
[data-testid="stSidebar"] [data-testid="stRadio"]>label{display:none}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:10px 11px;border-radius:9px;transition:background .15s;min-height:42px;font-size:13px}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#223c52}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:#233e50;border-left:3px solid #20d3c2;color:#5ae5d7}
[data-testid="stSidebar"] [data-testid="stRadio"] label>div:first-child{display:none}
[data-testid="stSidebar"] [data-testid="stExpander"]{background:#1b3045;border-color:#334b61}
[data-testid="stSidebar"] [data-testid="stAlert"]{background:#23384d;color:#d8e7fa}
.brand{display:flex;gap:10px;align-items:center;color:white;margin-bottom:20px}.brand-mark{width:35px;height:35px;flex-shrink:0;border-radius:13px 17px 13px 17px;background:conic-gradient(from 15deg,#164e68 0deg 60deg,#33c8ae 60deg 125deg,#398cf7 125deg 245deg,#2ce0c7 245deg 320deg,#18314a 320deg);transform:rotate(-12deg)}
.brand-title{font-size:18px;font-weight:750;line-height:1.3}.brand-sub{color:#adc1dc;font-size:10px;line-height:1.5}
.nav-foot{margin-top:22px;padding:14px;background:#203448;border:1px solid #2d465d;border-radius:14px;color:#bbcee4;font-size:11px;line-height:1.7}.nav-foot b{color:#49d8c1;font-size:14px}
h1{font-size:25px!important;letter-spacing:-.025em}h2{font-size:20px!important}h3{font-size:16px!important;letter-spacing:-.02em}
[data-testid="stMarkdownContainer"] p{font-size:13px;line-height:1.6}
[data-testid="stCaptionContainer"]{color:var(--muted);font-size:11px}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{font-size:13px;background:#fff;border-radius:9px}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border-color:#dce4f2!important;background:#fff!important;border-radius:9px!important}
.stButton>button,[data-testid="stFormSubmitButton"]>button,[data-testid="stPopover"]>button{border-radius:9px;font-size:12px;border-color:#dce4f2;min-height:36px}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primary"]{background:linear-gradient(110deg,#09bd8e,#069570);border:0;color:white}
[data-testid="stVerticalBlockBorderWrapper"]{background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 4px 18px #13274403}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);padding:14px;border-radius:11px}
[data-testid="stMetricLabel"]{color:#526383;font-size:12px}[data-testid="stMetricValue"]{color:var(--text);font-size:24px}
.stat-card{display:flex;align-items:center;gap:13px;min-height:94px;border:1px solid var(--line);border-radius:11px;background:linear-gradient(130deg,#fff,#f8fbff);padding:15px}
.stat-icon{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:43px;height:43px;border-radius:50%;background:#eef3ff;color:#4383ff;font-size:22px}
.stat-mint .stat-icon{background:#e4faf2;color:#00aa7c}.stat-orange .stat-icon{background:#fff0e9;color:#fa7946}.stat-purple .stat-icon{background:#f0ecff;color:#8261f0}.stat-mint{background:linear-gradient(120deg,#fff,#effbf7)}
.stat-label{font-size:11px;font-weight:600;color:#315a71}.stat-value{font-size:22px;font-weight:750;color:#12213b;line-height:1.45;white-space:nowrap}.stat-detail{font-size:10px;color:#7788a3}
.pill{display:inline-block;padding:4px 10px;border-radius:30px;background:#e6fbf3;color:#058857;font-size:10px;font-weight:600}.pill-orange{background:#fff0de;color:#a9530a}.pill-blue{background:#eaf3ff;color:#2165bc}.pill-gray{background:#eef1f5;color:#58647b}.pill-purple{background:#f0edff;color:#6751ca}
.client-row{padding:12px 13px;background:#fff;border-bottom:1px solid #edf1f7;min-height:113px}.client-row.selected{background:linear-gradient(110deg,#effdf7,#f6fffb);border-left:3px solid #33cda1;padding-left:10px}.client-row>div:first-child{display:flex;align-items:start;gap:8px}.client-row strong{font-size:12px;color:#14233e}.client-row p{font-size:10px;margin:3px 0 0 0;color:#6f80a0}.client-bottom{display:flex;justify-content:space-between;align-items:center;margin-top:5px}.client-bottom b{font-size:13px;font-weight:650}.client-bottom span{font-size:9px;color:#8190a8}
.st-key-client-list [data-testid="stButton"] button{width:100%;text-align:left;justify-content:space-between;font-size:10px;min-height:28px;border:0;color:#169976;background:#f7fbfa}
.st-key-client-list [data-testid="stVerticalBlock"]{gap:.2rem}
.workspace-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:8px}.workspace-heading h2{font-size:22px!important;font-weight:750;margin:0;line-height:1.3}.contact-line{font-size:11px;color:#526283;line-height:1.9;margin:8px 0 12px;overflow-wrap:anywhere}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:18px;border-bottom:1px solid #eef1f7}
[data-testid="stTabs"] [data-baseweb="tab"]{padding:10px 0;font-size:11px;height:38px}
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background:#16b887;height:2px}
.ai-box{background:linear-gradient(125deg,#f2efff,#f9faff);border:1px solid #d8d0ff;border-radius:10px;padding:15px;margin-bottom:14px;color:#37315f;font-size:12px;line-height:1.65}.ai-box b{display:block;color:#4e39af;margin-bottom:7px}.ai-box ul{padding-left:17px;margin:5px 0}.ai-box li{margin-bottom:7px}.ai-box .estimate{margin-top:8px;font-size:10px;color:#756da0}
.top-status{font-size:10px;color:#7886a2;padding-top:8px;line-height:1.7}.status-dot{display:inline-block;width:6px;height:6px;border-radius:100%;background:#20c77e;margin-right:5px}.status-dot.off{background:#97a6bb}
.user-profile{display:flex;gap:8px;align-items:center;justify-content:flex-end;font-size:11px;color:#243554;padding:3px 0}.user-profile span{display:block;font-size:10px;color:#7b87a4}.avatar{display:flex;align-items:center;justify-content:center;width:33px;height:33px;flex-shrink:0;border-radius:50%;color:#0a987d;background:#e5f8f2;font-size:14px;font-weight:700}
.st-key-topbar{background:white;border-bottom:1px solid var(--line);padding:10px 0 13px;margin-bottom:4px}.st-key-topbar [data-testid="stTextInput"] label{display:none}.st-key-topbar [data-testid="stPopover"] button{background:#f8faff;white-space:normal}
.st-key-workspace-title{display:none}.st-key-client-detail [data-testid="stMetricValue"]{font-size:18px}.st-key-client-detail [data-testid="stMetric"]{padding:10px}
.st-key-contact-task{background:linear-gradient(115deg,#fffaf0,#fff5df);border-color:#ffe3a8;padding:10px}
.st-key-contact-task [data-testid="stForm"]{border:0;padding:0;background:transparent}
.st-key-draft-panel [data-testid="stTextArea"] textarea{line-height:1.75;min-height:210px}
[data-testid="stCode"]{border:1px solid #e6ecf4;border-radius:8px}
.empty-hero{padding:36px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(115deg,#fff,#f1fcf8);margin-top:18px;max-width:1000px}.empty-hero h2{font-size:28px!important;color:#162d4a}.empty-hero p{font-size:14px;color:#63758f;max-width:620px;line-height:1.8}
@media(min-width:1100px){.st-key-workspace [data-testid="stHorizontalBlock"]{align-items:stretch}.st-key-client-list,.st-key-client-detail,.st-key-draft-panel{min-height:760px}}
@media(max-width:1099px){.st-key-workspace>[data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-workspace>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}.stat-value{font-size:19px}.stat-card{padding:11px;gap:8px}}
@media(max-width:640px){.block-container{padding:4rem .75rem 1rem}.st-key-topbar [data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-topbar [data-testid="stColumn"]{min-width:100%!important;flex:1 1 100%!important}.user-profile{justify-content:flex-start}.stat-card{min-height:80px}.workspace-heading{flex-wrap:wrap}.empty-hero{padding:22px}.stat-value{font-size:20px}}

[data-testid="stSidebarHeader"]{height:36px}
[data-testid="stSidebarUserContent"]{padding:0 14px 20px}
.brand{margin-top:-10px;gap:8px}.brand-title{font-size:16px}.brand-sub{font-size:9px}
[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p{font-size:18px!important;font-weight:750;line-height:1.3}
[data-testid="stTextInputRootElement"]{border:1px solid #dce4f2!important;border-radius:9px!important;background:white!important}
[data-testid="stTextAreaRootElement"]{border:1px solid #dce4f2!important;border-radius:9px!important;background:white!important}
.client-row{min-height:100px;padding:11px 12px}.client-row strong{font-size:12px}
.st-key-send-whatsapp a{background:#08b889!important;color:white!important;border:0!important}
.st-key-send-telegram a{background:#3388f7!important;color:white!important;border:0!important}
@media(max-width:1099px){.st-key-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}}

[data-testid="stSidebar"] [data-testid="stRadioOption"]>div>div:first-child{display:none}

[data-testid="stLayoutWrapper"]:has(>.st-key-workspace-title){display:none}
.st-key-topbar{padding-top:0;padding-bottom:10px}
.stat-value{font-size:clamp(16px,1.3vw,22px);white-space:normal;overflow-wrap:anywhere}
@media(max-width:1099px){
.st-key-kpi-rack>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:10px}
.st-key-kpi-rack>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 calc(50% - 10px)!important;min-width:calc(50% - 10px)!important}
.st-key-topbar [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
.st-key-topbar [data-testid="stColumn"]{flex:1 1 180px!important;min-width:180px!important}
.st-key-topbar [data-testid="stColumn"]:first-child{flex:1 1 100%!important;min-width:100%!important}
}
@media(max-width:640px){
.st-key-kpi-rack>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}
.st-key-topbar [data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}
.stat-value{font-size:21px}
}

/* Keep hit targets in normal document flow: no invisible overlay buttons. */
.stButton>button,[data-testid="stFormSubmitButton"]>button,[data-testid="stPopover"]>button,[data-testid="stLinkButton"] a{min-height:44px;cursor:pointer}
.st-key-client-list [data-testid="stButton"] button{min-height:44px;border:1px solid #dce7e2;border-radius:8px;color:#08765d;background:#f3fbf7;padding:8px 10px;font-size:12px;justify-content:center}
.st-key-client-list [data-testid="stButton"] button:hover{background:#e3f7ed;border-color:#33bb91}
.st-key-client-list [data-testid="stButton"] button:focus-visible{outline:2px solid #16b887;outline-offset:2px}
.st-key-open_settings button{background:#eff8f5;color:#13755b;border:1px solid #cfe8df;width:100%}
[data-testid="stButton"] button:disabled,[data-testid="stFormSubmitButton"] button:disabled{cursor:not-allowed}

.st-key-device-store{height:0;min-height:0;overflow:hidden}
[data-testid="stLayoutWrapper"]:has(>.st-key-device-store){height:0;min-height:0}
.st-key-product-workspace .stButton>button{text-align:left;white-space:normal;justify-content:flex-start;min-height:44px}
@media(max-width:1099px){.st-key-product-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-product-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}}
@media(max-width:640px){.st-key-crm-blocks [data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-crm-blocks [data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}}

/* Product analytics: the quiet two-panel workspace supplied by the user.
   Keyed containers keep these styles out of the other CRM sections. */
.stApp:has(.st-key-product-design-page){background:#f5f7f9;color:#1e2d3d}
.stApp:has(.st-key-product-design-page) [data-testid="stSidebar"]{background:#142b3f;min-width:232px;max-width:232px}
.stApp:has(.st-key-product-design-page) .brand-title{font-size:14px}
@media(max-width:1150px){.stApp:has(.st-key-product-design-page) [data-testid="stSidebar"]{min-width:205px;max-width:205px}}
.st-key-product-design-page{--pd-text:#1e2d3d;--pd-muted:#728295;--pd-line:#e3eaf0;--pd-accent:#078b76;--pd-selected:#e8f5f2;min-width:0;color:var(--pd-text)}
.st-key-product-design-page>[data-testid="stVerticalBlock"],.st-key-product-design-page{gap:12px}
.st-key-product-design-page [data-testid="stColumn"],.st-key-product-design-page [data-testid="stLayoutWrapper"]{min-width:0}
.st-key-product-design-page [data-testid="stMarkdownContainer"] p{font-size:13px;line-height:1.55;color:var(--pd-text)}
.st-key-product-design-page [data-testid="stCaptionContainer"]{font-size:12px;line-height:1.5;color:var(--pd-muted)}
.st-key-product-design-page [data-testid="stCaptionContainer"] p{font-size:12px!important;line-height:1.45;color:var(--pd-muted)!important;margin:0}
.st-key-product-design-page h1,.st-key-product-design-page .pd-title{font-size:24px!important;font-weight:700;line-height:1.25;letter-spacing:-.035em;color:var(--pd-text);margin:0;padding:0}
.st-key-product-design-page h2,.st-key-product-design-page h3,.st-key-product-design-page .st-key-product-design-panel-title{font-size:14px!important;line-height:1.4;letter-spacing:0;color:var(--pd-text);font-weight:700;padding:0;margin:0}
.st-key-product-design-heading{padding:8px 0 0;gap:6px}
.st-key-product-design-header>[data-testid="stHorizontalBlock"],.st-key-product-design-header>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{gap:20px;align-items:flex-end}
.st-key-product-design-header [data-testid="stColumn"]{min-width:0!important}
.st-key-product-design-page .pd-eyebrow{font-size:11px;line-height:1.5;font-weight:700;letter-spacing:.045em;text-transform:uppercase;color:var(--pd-accent);margin-bottom:4px}
.st-key-product-design-page .pd-subtitle{font-size:13px;line-height:1.5;color:var(--pd-muted);margin:5px 0 0}
.st-key-product-design-page .pd-selected-label{font-size:10px;line-height:1.5;text-transform:uppercase;letter-spacing:.07em;color:var(--pd-muted);font-weight:700;overflow-wrap:anywhere}
.st-key-product-design-page .pd-product-title{font-size:17px;line-height:1.4;font-weight:650;letter-spacing:-.015em;color:var(--pd-text);margin:5px 0;overflow-wrap:anywhere}
.st-key-product-design-page .pd-product-meta{font-size:12px;line-height:1.5;color:var(--pd-muted);overflow-wrap:anywhere}
.st-key-product-design-page .pd-chip{display:inline-flex;align-items:center;gap:5px;background:#fff;border:1px solid var(--pd-line);border-radius:7px;color:#4a6074;font-size:12px;line-height:1.4;padding:5px 9px;max-width:100%;overflow-wrap:anywhere}
.st-key-product-design-page .pd-chip.selected{background:var(--pd-selected);border-color:#9ccfc5;color:#087b69;font-weight:650}
.st-key-product-design-controls>[data-testid="stHorizontalBlock"],.st-key-product-design-controls>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{gap:12px;align-items:flex-end}
.st-key-product-design-controls [data-testid="stColumn"]{min-width:0!important}
.st-key-product-design-filters{background:#fff;border:1px solid var(--pd-line);border-radius:12px;padding:12px 14px;box-shadow:0 2px 10px #1c32440b}
.st-key-product-design-filters>[data-testid="stHorizontalBlock"],.st-key-product-design-filters>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{gap:10px;align-items:center;flex-wrap:wrap}
.st-key-product-design-filters>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-filters>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 150px!important;min-width:150px!important}
.st-key-product-design-workspace>[data-testid="stHorizontalBlock"],.st-key-product-design-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{gap:16px;align-items:flex-start}
.st-key-product-design-workspace>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 0!important;min-width:0!important}
.st-key-product-design-catalog,.st-key-product-design-details{background:#fff;border:1px solid var(--pd-line);border-radius:12px;padding:16px;box-shadow:0 2px 10px #1c32440b;min-width:0;gap:12px}
.st-key-product-design-page [data-testid="stTextInputRootElement"],.st-key-product-design-page [data-testid="stTextAreaRootElement"]{background:#fff!important;border:1px solid var(--pd-line)!important;border-radius:8px!important}
.st-key-product-design-page [data-baseweb="select"]>div{background:#fff!important;border:1px solid var(--pd-line)!important;border-radius:8px!important}
.st-key-product-design-page [data-testid="stTextInput"] input,.st-key-product-design-page [data-testid="stTextArea"] textarea,.st-key-product-design-page [data-testid="stSelectbox"] input{font-size:13px;color:var(--pd-text)}
.st-key-product-design-page [data-testid="stWidgetLabel"] p{font-size:12px;line-height:1.4;color:#52677a}
.st-key-product-design-page [data-testid="stCheckbox"] label{min-height:36px;align-items:center}
.st-key-product-design-page [data-testid="stCheckbox"] label p{font-size:12px}
.st-key-product-design-page [data-testid="stButton"] button,.st-key-product-design-page [data-testid="stDownloadButton"] button,.st-key-product-design-page [data-testid="stPopover"] button,.st-key-product-design-page [data-testid="stFormSubmitButton"] button{font-size:12px;min-height:36px;border:1px solid var(--pd-line);border-radius:8px;color:#42586c;background:#fff;box-shadow:none;white-space:normal;line-height:1.4;padding:7px 12px}
.st-key-product-design-page [data-testid="stButton"] button:hover,.st-key-product-design-page [data-testid="stDownloadButton"] button:hover,.st-key-product-design-page [data-testid="stPopover"] button:hover{border-color:#9ccfc5;background:#f3f9f7;color:#087b69}
.st-key-product-design-page [data-testid="stButton"] button[kind="primary"],.st-key-product-design-page [data-testid="stFormSubmitButton"] button[kind="primary"]{border-color:var(--pd-accent);background:var(--pd-accent);color:#fff}
.st-key-product-design-page [data-testid="stButton"] button[kind="primary"]:hover{background:#077763;border-color:#077763;color:#fff}
.st-key-product-design-page button:focus-visible,.st-key-product-design-page a:focus-visible{outline:2px solid var(--pd-accent);outline-offset:3px}
.st-key-product-design-page [data-testid="stTextInputRootElement"]:focus-within,.st-key-product-design-page [data-baseweb="select"]:focus-within>div{outline:2px solid #078b7673;outline-offset:2px}
.st-key-product-design-page button:disabled{color:#7a8996!important;background:#f6f8fa!important;border-color:var(--pd-line)!important;cursor:not-allowed;opacity:1}
.st-key-product-design-period [data-testid="stButtonGroup"]>div{gap:6px;flex-wrap:wrap}
.st-key-product-design-period [data-testid="stButtonGroup"] button{font-size:12px;min-height:32px;padding:6px 9px;border:1px solid var(--pd-line);border-radius:7px;color:#52677a;background:#fff;line-height:1.4}
.st-key-product-design-period [data-testid="stButtonGroup"] button[aria-pressed="true"]{background:var(--pd-selected);border-color:#9ccfc5;color:#087b69;font-weight:650}
.st-key-product-design-period [data-testid="stButtonGroup"] button:hover{border-color:#9ccfc5;background:#f3f9f7}
.st-key-product-design-metrics>[data-testid="stHorizontalBlock"],.st-key-product-design-metrics>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{gap:9px;flex-wrap:nowrap}
.st-key-product-design-metrics>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-metrics>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 0!important;min-width:0!important;width:calc((100% - 18px)/3)!important;max-width:calc((100% - 18px)/3)!important}
.st-key-product-design-metrics [data-testid="stMetric"]{padding:11px;border:1px solid var(--pd-line);border-radius:9px;background:#fff;min-width:0;box-shadow:none}
.st-key-product-design-metrics [data-testid="stMetricLabel"]{font-size:11px;color:var(--pd-muted)}
.st-key-product-design-metrics [data-testid="stMetricLabel"] p{font-size:11px!important;line-height:1.4;color:var(--pd-muted)}
.st-key-product-design-metrics [data-testid="stMetricValue"]{font-size:20px!important;color:var(--pd-text);font-weight:700;letter-spacing:-.025em;font-variant-numeric:tabular-nums;white-space:normal;overflow-wrap:anywhere}
.st-key-product-design-metrics [data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p{font-size:20px!important;line-height:1.35;color:var(--pd-text);font-weight:700;font-variant-numeric:tabular-nums;white-space:normal;overflow-wrap:anywhere}
.st-key-product-design-page [data-testid="stDataFrame"]{max-width:100%;min-width:0;border:1px solid var(--pd-line);border-radius:8px;overflow:auto;font-size:12px;font-variant-numeric:tabular-nums}
.st-key-product-design-hint,.st-key-product-design-page .pd-hint{border-radius:9px;padding:12px 14px;background:#f0f6f7;border:1px solid #e3ecec;color:#536c78;font-size:12px;line-height:1.55;overflow-wrap:anywhere}
.st-key-product-design-hint [data-testid="stMarkdownContainer"] p{color:#536c78;font-size:12px;margin:0}
.st-key-product-design-hint b,.st-key-product-design-page .pd-hint b{color:#207d71}
@media(max-width:1249px){
 .st-key-product-design-workspace>[data-testid="stHorizontalBlock"],.st-key-product-design-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-wrap:wrap}
 .st-key-product-design-workspace>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-workspace>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}
 .st-key-product-design-controls>[data-testid="stHorizontalBlock"],.st-key-product-design-controls>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-wrap:wrap}
 .st-key-product-design-controls>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-controls>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 170px!important;min-width:170px!important}
}
@media(max-width:1099px){
 .st-key-product-design-header>[data-testid="stHorizontalBlock"],.st-key-product-design-header>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:12px}
 .st-key-product-design-header>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-header>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}
}
@media(max-width:640px){
 .st-key-product-design-page h1,.st-key-product-design-page .pd-title{font-size:22px!important}
 .st-key-product-design-catalog,.st-key-product-design-details{padding:12px;gap:12px}
 .st-key-product-design-filters{padding:10px}
 .st-key-product-design-filters>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-filters>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 calc(50% - 10px)!important;min-width:calc(50% - 10px)!important}
 .st-key-product-design-controls>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-controls>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 calc(50% - 12px)!important;min-width:calc(50% - 12px)!important}
 .st-key-product-design-controls>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child,.st-key-product-design-controls>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child{flex:1 1 100%!important;min-width:100%!important}
 .st-key-product-design-page [data-testid="stButton"] button,.st-key-product-design-page [data-testid="stDownloadButton"] button,.st-key-product-design-page [data-testid="stPopover"] button,.st-key-product-design-page [data-testid="stFormSubmitButton"] button,.st-key-product-design-period [data-testid="stButtonGroup"] button{min-height:44px}
 .st-key-product-design-page [data-testid="stCheckbox"] label{min-height:44px}
 .st-key-product-design-page [data-testid="stTextInputRootElement"],.st-key-product-design-page [data-baseweb="select"]>div{min-height:44px}
 .st-key-product-design-metrics>[data-testid="stHorizontalBlock"],.st-key-product-design-metrics>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{gap:6px}
 .st-key-product-design-metrics>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-product-design-metrics>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:calc((100% - 12px)/3)!important;max-width:calc((100% - 12px)/3)!important}
 .st-key-product-design-metrics [data-testid="stMetric"]{padding:8px 7px}
 .st-key-product-design-metrics [data-testid="stMetricValue"],.st-key-product-design-metrics [data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p{font-size:16px!important}
 .st-key-product-design-metrics [data-testid="stMetricLabel"] p{font-size:10px!important;white-space:normal}
 .st-key-product-design-page .pd-product-title{font-size:16px}
}
/* Dashboard: dense file-list rhythm, native inputs and grid hit targets. */
.st-key-dashboard-inbox{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px}
.st-key-dashboard-inbox [data-testid="stVerticalBlock"]{gap:8px}
.st-key-dashboard-inbox [data-testid="stWidgetLabel"] p{font-size:11px;line-height:1.4}
.st-key-dashboard-inbox [data-testid="stTextInput"] input,.st-key-dashboard-inbox [data-baseweb="select"]{font-size:12px}
.st-key-dashboard-inbox [data-testid="stDataFrame"]{border-radius:7px;border:1px solid #e5eaf2;max-width:100%}
.dashboard-register{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 0 6px;border-top:1px solid #edf1f7;font-size:11px;color:#7281a3}
.dashboard-register b{color:#344762;font-size:10px;letter-spacing:.08em}
@media(max-width:640px){
 .st-key-dashboard-inbox{padding:12px}
 .st-key-dashboard-inbox [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:8px}
 .st-key-dashboard-inbox [data-testid="stColumn"]{flex:1 1 100%!important;min-width:100%!important}
 .dashboard-register{align-items:flex-start;flex-direction:column;gap:3px}
}
</style>'''
