// A5 booklet: 永續企業治理 — 給屏東基督教醫院的永續治理線索
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, AlignmentType, PageBreak,
  Footer, Header, PageNumber, BorderStyle, LevelFormat, TabStopType, LeaderType,
  VerticalPositionAlign,
} = require("docx");

const EA = "微軟正黑體";
const LAT = "Calibri";
const NAVY = "1F3A4D", SEPIA = "8C6239", GOLD = "C8A356", RED = "A4432E",
      GRAY = "6E6A60", TEXT = "2B2B28";

const F = { ascii: LAT, hAnsi: LAT, eastAsia: EA };

function R(text, o = {}) {
  return new TextRun({ text, font: F, size: o.size ?? 19, bold: o.bold, color: o.color ?? TEXT, italics: o.i });
}
// body paragraph; parts: string or [text, opts]
function P(parts, o = {}) {
  const runs = (Array.isArray(parts) ? parts : [parts]).map(p =>
    typeof p === "string" ? R(p) : R(p[0], p[1]));
  return new Paragraph({
    children: runs,
    alignment: o.align ?? AlignmentType.JUSTIFIED,
    spacing: { line: 300, lineRule: "auto", after: o.after ?? 120, before: o.before ?? 0 },
    indent: o.indent,
    numbering: o.num ? { reference: o.num, level: 0 } : undefined,
    border: o.border,
    keepNext: o.keepNext,
    pageBreakBefore: o.pbb,
  });
}
function H1(text, opts = {}) {
  return new Paragraph({
    pageBreakBefore: opts.pbb !== false,
    keepNext: true,
    spacing: { before: 120, after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: GOLD, space: 6 } },
    children: [new TextRun({ text, font: F, size: 30, bold: true, color: NAVY })],
  });
}
function H2(text) {
  return new Paragraph({
    keepNext: true,
    spacing: { before: 220, after: 130 },
    children: [new TextRun({ text, font: F, size: 23, bold: true, color: SEPIA })],
  });
}
function KICKER(text) { // small letterspaced label
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 160 },
    children: [new TextRun({ text, font: F, size: 17, color: GOLD, bold: true, characterSpacing: 60 })],
  });
}
function IMG(file, wpx, hpx, caption, o = {}) {
  const data = fs.readFileSync(`img/${file}`);
  const out = [new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: o.before ?? 160, after: 60 },
    children: [new ImageRun({ type: "png", data, transformation: { width: wpx, height: hpx } })],
  })];
  if (caption) out.push(new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: caption, font: F, size: 16, color: GRAY })],
  }));
  return out;
}
function CALLOUT(parts, o = {}) {
  return P(parts, {
    ...o,
    indent: { left: 240, right: 120 },
    border: { left: { style: BorderStyle.SINGLE, size: 14, color: GOLD, space: 12 } },
  });
}
const W = 438; // content-width image in px (≈116mm)

// ---------------- content ----------------
const children = [];

// ===== cover =====
children.push(
  new Paragraph({ spacing: { before: 700, after: 0 }, children: [] }),
  KICKER("永 續 企 業 治 理"),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "活過幾百年的企業，", font: F, size: 40, bold: true, color: NAVY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: "到底靠什麼活著、又敗在哪裡", font: F, size: 40, bold: true, color: NAVY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 340 },
    children: [new TextRun({ text: "給屏東基督教醫院的永續治理線索", font: F, size: 24, color: SEPIA })],
  }),
  ...IMG("cover.png", W, Math.round(W * 980 / 1440), null),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 300, after: 60 },
    children: [new TextRun({ text: "屏東基督教醫院", font: F, size: 21, color: TEXT })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "2026 年 9 月", font: F, size: 18, color: GRAY })],
  }),
);

// ===== TOC =====
const tocEntries = [
  ["簡短摘要", "3"],
  ["主要發現", "5"],
  ["一、核心對照：柯達 vs 富士", "7"],
  ["二、超長壽企業的存活模式", "9"],
  ["三、失敗組解剖：四種可預測的死法", "11"],
  ["四、醫院與非營利組織的長壽機制", "13"],
  ["五、屏基的定位與永續風險", "15"],
  ["建議（分階段、可操作）", "17"],
  ["注意事項（限制與存疑）", "19"],
  ["附錄：自我檢視的診斷性問題清單", "20"],
];
children.push(
  new Paragraph({
    pageBreakBefore: true, spacing: { before: 200, after: 260 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: GOLD, space: 6 } },
    children: [new TextRun({ text: "目錄", font: F, size: 30, bold: true, color: NAVY })],
  }),
  ...tocEntries.map(([t, p]) => new Paragraph({
    spacing: { after: 150 },
    tabStops: [{ type: TabStopType.RIGHT, position: 6570, leader: LeaderType.DOT }],
    children: [
      new TextRun({ text: t, font: F, size: 20, color: TEXT }),
      new TextRun({ text: "\t" + p, font: F, size: 20, color: SEPIA }),
    ],
  })),
  new Paragraph({ spacing: { before: 320, after: 0 }, children: [] }),
  new Paragraph({
    spacing: { before: 200 },
    indent: { left: 240, right: 120 },
    border: { left: { style: BorderStyle.SINGLE, size: 14, color: GOLD, space: 12 } },
    children: [new TextRun({ text: "本冊由研究報告重新排版而成（A5）。因所處環境無法取得外部歷史照片授權檔案，冊內圖片為依據史實重繪之示意插畫與資料圖表。", font: F, size: 16, color: GRAY })],
  }),
);

// ===== 簡短摘要 =====
children.push(H1("簡短摘要"));
children.push(P([
  ["柯達與富士的差別不是「誰先做數位」", { bold: true }],
  "（柯達 1975 年就發明了數位相機），而是「把自己定義成產品公司還是能力公司」：柯達守著「膠片這個產品」、用股票回購與股利討好股東；富士盤點出 70 多項底層技術（膠原蛋白／明膠化學、奈米分散、抗氧化、光學塗佈），把它們搬到化妝品、醫療、再生醫學與半導體材料上重新應用，因此柯達 2012 年破產、富士至今興旺。",
  ["對醫院的第一個線索是：你的核心資產不是「病床」這個產品，而是一組可遷移的能力。", { bold: true, color: NAVY }],
]));
children.push(P([
  ["超長壽組織的共同結構", { bold: true }],
  "（Merck 1668、Zeiss／Bosch 基金會、Stora Enso 1288、以及活了 600–900 年的宗教型醫院）是：所有權穩定（家族憲章或基金會持股，隔絕季度壓力）＋財務保守（怕負債、留現金）＋使命凝聚（清楚的存在理由）＋容忍邊緣試驗。屏基身為「醫療財團法人」，在所有權光譜上其實已經接近 Bosch、Zeiss 這類「基金會企業」——這是它最大的結構優勢，但也帶來特定盲點。",
]));
children.push(P([
  ["失敗幾乎都不是「意外」，而是四種可預測的死法：", { bold: true }],
  "（a）把產品當成能力來守（柯達、金剛組）；（b）多角化失焦／併購消化不良（GE、西屋）；（c）財務槓桿與短期資本壓力（雷曼、Hudson's Bay、金剛組的房地產借貸）；（d）私募基金掏空（Steward Health Care 2024 年破產，是「醫院規模變大反而死掉」的當代鐵證）。",
]));
children.push(CALLOUT([
  ["屏基正在蓋新大樓、床數要從 676 床擴到 861 床、已向銀行貸款 34 億元——這正是上述第（c）類死因最容易發芽的時刻，本報告的診斷清單即為此而寫。", { color: NAVY, bold: true }],
]));
children.push(...IMG("timeline.png", W, Math.round(W * 980 / 1440), "圖 1｜組織壽命對照表（578–2026，依據公開史料繪製）"));

// ===== 主要發現 =====
children.push(H1("主要發現"));
const findings = [
  [["柯達的致命點不是技術落後，而是「先射殺自己金雞母」的意願為零。", { bold: true }],
   "柯達工程師 Steven Sasson 在 1975 年就造出全球第一台數位相機，1979 年內部報告甚至預測數位將在 2010 年前取代膠片，但高層把它當「可愛的玩具，別聲張」，因為怕侵蝕高毛利的膠片與沖印生意。依 CNNMoney 2012/1/19 對其 Chapter 11 文件的報導，柯達承認「有超過 10 萬名債權人、負債總額 67.5 億美元」（資產約 51 億美元、最大債權人為 Bank of New York Mellon、逾 6.5 億美元）；市值曾在 1997 年 2 月達 310 億美元高峰。"],
  [["富士做了柯達不敢做的三件事：", { bold: true }],
   "(i) 承認膠片本業會消失、快速砍成本（VISION 75，2004 年由 CEO 古森重隆 Shigetaka Komori 推動，為 75 週年命名）；(ii) 花 18 個月盤點全公司技術、與全球市場需求對照，找出 70 多項可遷移技術；(iii) 把這些技術搬進新市場——Astalift 化妝品（膠原蛋白＋抗氧化＋奈米分散，膠片有超過一半成分是膠原蛋白）、醫療影像與再生醫學、以及半導體材料（光阻劑、CMP 研磨液）。富士現行 VISION2030 已把 2030 財年營收目標拉到 4 兆日圓等級。"],
  [["兩家對「能力」定義不同：", { bold: true }],
   "柯達問「我們怎麼繼續賣影像產品」；富士問古森重隆的那句話——「我們到底是什麼？」答案不是「照相公司」，而是「精通先進化學、光學、奈米技術與精密製造的公司」。這是「以產品定義自己」與「以能力定義自己」的分水嶺。"],
  [["超長壽企業的所有權結構高度一致地「抗短期化」：", { bold: true }],
   "Merck（1668，家族透過 E. Merck KG 持股 70.3%、公眾持 29.7% 且無投票權；約 156–157 位家族股東橫跨第 10–13 代、單一成員持股不超過 2–3%、家族契約下不得對外出售股權；家族憲章始於 1888 年，逾 5 億歐元交易需家族董事會核准）；Bosch（基金會持股約 92%）；Zeiss（1889 年 Ernst Abbe 交付基金會）；Novo Nordisk（基金會透過 Novo Holdings 握有約 28% 股本但約 77% 投票權）；Carlsberg、IKEA、Rolex、Tata 皆為基金會持有。丹麥有約一千家「企業基金會」。"],
  [["失敗組的解剖給出可辨識的死亡模式：", { bold: true }],
   "金剛組（578–2006，1,428 年）不是敗在做廟的手藝，而是 1980 年代泡沫期借錢炒房地產、泡沫破後被債務壓垮；Hudson's Bay（1670–2025，355 年）被私募基金 NRDC 掏空、賣掉旗下不動產、背上租金與逾 20 億美元債務後於 2025 年清算；GE 在 2024 年 4 月正式拆成三家（航空、能源、醫療），結束了百年綜合集團模式；Steward Health Care 在 Cerberus 私募基金與 Medical Properties Trust 的售後回租操作下破產。"],
  [["世界上最長壽的機構就是宗教使命型醫院：", { bold: true }],
   "巴黎 Hôtel-Dieu（傳 651 年創立）、倫敦 St Bartholomew's（1123 年）、佛羅倫斯 Santa Maria Nuova（1288 年，全球最古老仍營運的醫院）。依 Barts Health NHS Trust 官方史料，St Bartholomew's「在同一地點提供不間斷的病人照護，比英格蘭任何其他醫院都久……1123 年由 Rahere 創立……並於 2023 年慶祝 900 週年」，且在 1539 年亨利八世解散修道院後獲准續存（1546–47 年獲撥產）。它們的長壽引擎正是「清楚而超越利潤的存在理由」——這與屏基「藉著神的愛與能力，經由醫療等服務，恢復人的健康與尊嚴」的宗旨同源。"],
  [["Mayo Clinic（1864）把使命寫進制度：", { bold: true }],
   "核心價值「病人的需要優先」（The needs of the patient come first）不是口號，而是用「醫師純薪水制」（超過 40 年）落實——醫師開 4 台刀或 0 台刀薪水一樣，轉診給更適合的同事不損失收入，因此移除了「過度醫療」的財務誘因。這是「使命制度化」的教科書級案例。"],
  [["屏基本身在長壽結構光譜上位置良好，但正走到高風險擴張期：", { bold: true }],
   "屏基 1953 年由美國宣教士白信德創辦畢士大診所、1956 年由挪威協力會接辦，早期救治痲瘋病、肺結核與小兒麻痺；「台灣小兒麻痺之父」畢嘉士（Olav Bjørgaas，1926–2019）是精神象徵。今為醫療財團法人、區域教學醫院、現址 676 床。正在蓋瑞光路新院區智能醫療大樓（近 7 萬平方公尺、2026 年預計完工），完工後床數達 861 床、現址轉型長照，已向銀行貸款 34 億元、「無財團奧援」自籌。"],
];
findings.forEach(f => children.push(P(f, { num: "findings" })));

// ===== 一、柯達 vs 富士 =====
children.push(H1("一、核心對照：柯達 vs 富士——同樣的化學底子，兩種命運"));
children.push(P([
  ["同一個起點。", { bold: true }],
  "兩家公司都以銀鹽鹵化物膠片為核心，都掌握精密塗佈（在約 20 微米厚的膠原蛋白膜上乳化分散上百種功能微粒、疊約 20 層）、光學、與大規模精密化學製造。差別從「如何定義自己」開始分岔。",
]));
children.push(...IMG("kodak_fuji.png", W, Math.round(W * 900 / 1440), "圖 2｜同一卷底片，兩種命運（依據公開史料繪製之示意圖）"));
children.push(H2("柯達的三個致命決策"));
children.push(P([
  ["1. 產品導向的自我定義。", { bold: true }],
  "柯達歷任 CEO 都把自己看成「從類比走向數位的照相公司」——邏輯上正確、卻致命地狹窄。1975 年 Sasson 造出數位相機、1979 年內部報告預測 2010 年前數位取代膠片，高層卻要 Sasson「別張揚」，因為數位會侵蝕自家高毛利膠片與沖印生意。這是典型的「不願先殺死自己的金雞母」。",
]));
children.push(P([
  ["2. 有錢卻投錯地方。", { bold: true }],
  "柯達 1988 年以 51 億美元買下 Sterling Drug 製藥（想把自家幾十萬種化合物變成藥），六年後拆分賣掉（賣給 Sanofi 16.75 億、賣給 SmithKline Beecham 29.25 億美元）——雖有來源估算整體其實小賺，但它耗掉六年管理注意力與資本，且與影像本業毫無綜效。柯達長年以股利與股票回購回饋股東，資本沒有系統性投入到「能力再應用」。",
]));
children.push(P([
  ["3. 結局。", { bold: true }],
  "2012 年 1 月破產（負債 67.5 億美元、逾 10 萬債權人）；曾雇 14.5 萬人。2013 年以較小的商業印刷公司之姿走出破產，退出數位相機。此外，高額退休金與遺留成本（legacy cost）也是壓垮它的主因之一。",
]));
children.push(H2("富士的轉型公式（可直接抄給醫院）"));
children.push(P([
  ["VISION 75（2004，古森重隆）：", { bold: true }],
  "明說目標是「把富士從災難中救出來，確保它作為年營收 2–3 兆日圓的領先企業繼續存活」。前提是承認膠片本業會消失（膠片市場萎縮比預期快得多），並快速砍成本、裁員。",
]));
children.push(P([
  ["技術盤點 → 鄰接市場再應用：", { bold: true }],
  "花 18 個月把全公司技術做一次總清點，對照全球市場需求，找出 70 多項可遷移技術，落到三大新戰場：",
]));
children.push(P([["化妝品（Astalift）：", { bold: true, color: SEPIA }], "膠片褪色的成因（紫外線氧化）與皮膚老化同源；膠片一半成分是膠原蛋白；把穩定蝦紅素（astaxanthin）的奈米乳化分散技術直接搬過來。"], { indent: { left: 240 } }));
children.push(P([["醫療與再生醫學：", { bold: true, color: SEPIA }], "X 光片起家（1936 年）、1983 年全球首創數位 X 光影像；後收購 Cellular Dynamics、整合日本 Tissue Engineering，跨入 iPS 細胞、細胞培養基、生物藥 CDMO。"], { indent: { left: 240 } }));
children.push(P([["半導體與顯示材料：", { bold: true, color: SEPIA }], "塗佈技術變成偏光板保護膜（FUJITAC）與液晶光學膜；電子材料事業涵蓋光阻劑（含 EUV）、CMP 研磨液、後 CMP 清洗液，目標 2030 年電子材料營收 5,000 億日圓。"], { indent: { left: 240 } }));
children.push(CALLOUT([
  ["對「能力」的重新定義：", { bold: true, color: NAVY }],
  "不是「我們賣什麼產品」，而是「我們精通哪些底層能力」。這一句話的差別，就是破產與興旺的差別。",
]));

// ===== 二、超長壽企業 =====
children.push(H1("二、超長壽企業（200–500 年以上）的存活模式"));
children.push(P([
  ["學術基礎：Arie de Geus《The Living Company》", { bold: true }],
  "（原載《哈佛商業評論》1997 年 3–4 月號）。de Geus 在殼牌（Royal Dutch/Shell）主持的研究發現，全球有一批公司存活 100–700 年（團隊找到約 30 家、其中 27 家有完整史料，包括 DuPont、Mitsui、Kodak、Sumitomo、Siemens），而他原句指出「《財星》500 大企業的平均壽命只有 40 到 50 年」，並以瑞典 Stora「超過 700 年」為對照。",
]));
children.push(P(["長壽者共有四特徵：(1) 對環境敏感（持續學習、及早調整）；(2) 凝聚的認同（強文化、內部拔擢、員工有歸屬感）；(3) 容忍邊緣的實驗與怪咖（新事業常與本業無關，不由中央嚴控）；(4) 財務保守（厭惡負債、珍惜現金）。他明確指出，長壽公司「不把自己當成替股東生錢的機器，而當成活的社群」。"]));
children.push(H2("所有權與治理結構是關鍵變數"));
children.push(P([
  ["家族憲章型：Merck（1668）是活教材。", { bold: true }],
  "家族透過 E. Merck KG 持股 70.3%（公眾持 29.7% 且無投票權）、傳至第 13 代；1888 年就寫下第一部家族憲章（現約 150 頁、每 10 年更新、家族視為契約）；採雙董事會（非家族的公司董事會管營運、家族董事會做監督）；任何逾 5 億歐元的併購／處分需家族董事會核准；家族成員不得出售股權、單一成員持股不超過 2–3%。這套結構讓它能「以世代計、而非以季度計」思考。",
]));
children.push(P([
  ["基金會持有型：", { bold: true }],
  "Bosch（基金會約 92%）、Zeiss（1889 起交付基金會，利潤資助研究與社會而非股東）、Novo Nordisk（基金會經 Novo Holdings 握約 28% 股本、約 77% 投票權，章程強制維持控制權）、Carlsberg、IKEA、Rolex、Tata。丹麥有約一千家「企業基金會」——這是把「長期主義」寫進所有權結構的做法。",
]));
children.push(P([
  ["產業穩定＋轉型能力：Stora Enso（1288 銅礦→鐵→紙漿→包裝／生質材料）。", { bold: true }],
  "全球最古老的股權憑證（1288 年 Falun 銅礦，把 1/8 股權給西發特拉主教）就是它的起點；700 多年間一路轉業。這證明「長壽不是守著同一個產品，而是守著同一套組織與不斷換的產品」。",
]));
children.push(CALLOUT([
  ["為什麼所有權結構這麼重要——季度壓力的實證：", { bold: true, color: NAVY }],
  "多篇研究（含 Stephen J. Terry 2023 年《Econometrica》〈The Macro Impact of Short-Termism〉、HBS、FCLTGlobal、以及一篇專門以台灣為樣本的研究）一致發現：為了達成短期盈餘目標，經理人會砍 R&D；剛好「達標」的公司 R&D 成長明顯較低（約低 2.5%／年）。這解釋了為什麼「隔絕於股市季度壓力之外」的家族／基金會企業，更能做需要幾十年才回收的投資。財團法人醫院天生沒有股東與季度盈餘壓力——這正是屏基相對於私募基金醫院的結構性優勢。",
]));

// ===== 三、失敗組解剖 =====
children.push(H1("三、失敗組解剖：四種可預測的死法"));
children.push(P([
  ["(a) 把「產品」當成「能力」來守——柯達、金剛組。", { bold: true }],
  "金剛組（578 年創立，世界最古老企業，1,428 年）並非敗於蓋廟的手藝或需求消失，而是 1980 年代泡沫期舉債炒房地產、泡沫破後資產縮水、負債超過 40 億日圓（2005 年營收約 75 億日圓），2006 年清算、被高松建設收編。",
  ["教訓：再古老的手藝，也擋不住一次錯誤的財務槓桿。", { bold: true, color: RED }],
]));
children.push(...IMG("kongo_gumi.png", W, Math.round(W * 960 / 1440), "圖 3｜金剛組與五重塔（578–2006，依據史實繪製之示意圖）"));
children.push(P([
  ["(b) 多角化失焦／併購消化不良——GE、西屋。", { bold: true }],
  "GE 從綜合集團一路擴張，最終在 2024 年 4 月拆成三家獨立上市公司（GE Aerospace、GE Vernova、GE HealthCare），官方理由正是「各自聚焦、資本配置更靈活」——等於承認「什麼都做」的綜合模式走到盡頭。",
]));
children.push(P([
  ["(c) 財務槓桿與短期資本市場壓力——雷曼、Hudson's Bay。", { bold: true }],
  "Hudson's Bay（1670–2025）撐過了毛皮貿易終結、加拿大建國、兩次世界大戰，卻在被私募基金 NRDC 持有後，不動產被賣掉、背上高租金與逾 20 億美元債務，2025 年 3 月申請債權人保護、6 月全店關閉、355 年畫下句點。",
  ["掏空的不是市場，是資產負債表。", { bold: true, color: RED }],
]));
children.push(P([
  ["(d) 私募基金掏空醫療——Steward Health Care（醫院版鐵證）。", { bold: true }],
  "Cerberus 私募基金 2010 年買下、2016 年做「售後回租」（sale-leaseback，把醫院土地以 12.5 億美元賣給地產信託 MPT，換現金分紅），醫院從此背上不斷上漲的租金；Cerberus 與 CEO de la Torre 據報抽走約 13 億美元後於 2020 年退場。依 Private Equity Stakeholder Project 與 Gibbins Advisors 分析，Steward 於 2024/5/6 在德州南區破產法院聲請 Chapter 11，總負債逾 90 億美元（含對 MPT 的 66 億美元長期租金義務、近 10 億美元積欠廠商、2.9 億美元員工薪資），旗下 31 家醫院、橫跨 10 州、近 3 萬名員工，是「三十年來最大的醫院部門破產案」。",
]));
children.push(CALLOUT([
  ["這是「規模變大反而死掉」的醫療當代版：擴張本身沒殺死它，用擴張來套現的財務結構殺死了它。", { bold: true, color: NAVY }],
]));

// ===== 四、醫院與非營利組織 =====
children.push(H1("四、醫院與非營利組織的長壽機制"));
children.push(P([
  ["宗教使命型醫院是人類最長壽的組織之一。", { bold: true }],
  "巴黎 Hôtel-Dieu（傳 651 年）、倫敦 St Bartholomew's（1123 年，同址不間斷照護、2023 年滿 900 週年、熬過亨利八世 1539 年解散修道院、1666 倫敦大火、二戰轟炸）、佛羅倫斯 Santa Maria Nuova（1288 年，全球最古老仍營運醫院，由商人 Folco Portinari 創立、早期由修女照護）。它們共同的長壽引擎，是一個超越利潤、代代可傳承的「存在理由」——正是 de Geus 說的「凝聚認同」在宗教機構裡的極致形式，基督教的話來說是應回應共同的呼召。",
]));
children.push(...IMG("hospital.png", W, Math.round(W * 960 / 1440), "圖 4｜使命型醫院的九百年（依據史實繪製之示意圖）"));
children.push(P([
  ["Mayo Clinic：把使命變成制度，而非標語。", { bold: true }],
  "「病人的需要優先」透過三個制度落地：(1) 純薪水制（逾 40 年，醫師薪水不隨手術量或轉診變動，移除過度醫療誘因，2019 年研究顯示 96% 醫師薪酬落在模型預測區間、達成性別與種族薪酬平等）；(2) 團隊醫療（結構設計成合作而非階層）；(3) 理事會的責任是「理解、背書並確保這個核心價值被反覆強化」。前 CEO Cortese 說：領導層的責任是創造願景、讓人人擁有它、對齊組織——維護核心價值的責任在內部領導層，理事會的責任是確保它被強化。",
]));
children.push(P([
  ["台灣醫療財團法人治理脈絡。", { bold: true }],
  "依《醫療法》：醫療財團法人須設董事會、置董事長一人為法人代表（第 33 條）；董事 9–15 人，其中具醫事人員資格者不得低於 1/3、至少 1 名醫師，外國人不得超過 1/3，有配偶或三親等內親屬關係者不得超過 1/3（第 43 條）；董事每屆任期不得逾 4 年、連選連任者每屆不得超過 2/3（防「萬年董事會」）；醫療法人不得為保證人、資金不得貸與董事或個人、不得以資產為他人提供擔保（第 37 條）——這條正是防止 Steward 式掏空的法律防火牆。近年修法方向包括財務資訊公開透明、強化董事會治理、限制董事長連任、增設監察人與社會公正人士。教會醫院（如馬偕）另訂有董事會組織及議事章則，依醫療法第 33 條與捐助章程訂定。",
]));

// ===== 五、屏基 =====
children.push(H1("五、屏基的定位與永續風險"));
children.push(P([
  "屏基 1953 年由美國行道會宣教士白信德（Signe Berg）創辦「畢士大診所」，1956 年由挪威協力會（The Mission Alliance / NMA，挪威語 Misjonsalliansen）接辦。早期主力是痲瘋病、肺結核與小兒麻痺救治，非一般診療。挪威籍畢嘉士醫師（Olav Bjørgaas，1926–2019，「台灣小兒麻痺之父」，2008 年獲挪威聖奧拉夫勳章）是屏基使命精神的象徵：他看痲瘋病人不戴手套、讓病人優先看診以維護尊嚴、1960 年代自美國進口沙賓疫苗免費為屏東約 4,000 名孩童接種（台灣首次大規模接種）、1963 年成立全台第一所麻痺兒童之家（今勝利之家前身）、辦支架工廠自製鐵鞋。以其命名的畢嘉士基金會 2013 年成立，深耕屏東偏鄉長照並在非洲馬拉威推教育／健康／經濟計畫。屏基官網仍保有創院標語：",
  ["「哪裡有需要，就往哪裡去」。", { bold: true, color: SEPIA }],
]));
children.push(...IMG("pingtung.png", W, Math.round(W * 900 / 1440), "圖 5｜從畢士大診所到智能醫療大樓（1953–2026，示意圖）"));
children.push(P([
  "屏基今為醫療財團法人、區域教學醫院、現址 676 床、急診為重度級（屏北緊急醫療基地）。正在蓋瑞光路新院區「智能醫療大樓」（地下 2 層地上 11 層、總樓地板近 7 萬平方公尺、一般病床 499＋特殊病床 362，2026 年預計完工），完工後總床數達 861 床、現址轉型長照。",
  ["關鍵財務事實：新大樓「無財團奧援」、屏基自籌、已向銀行貸款 34 億元、仍有資金缺口對外募款。", { bold: true }],
]));
children.push(CALLOUT([
  ["診斷性判斷：", { bold: true, color: NAVY }],
  "屏基在永續結構光譜上，因為是「使命清楚＋財團法人（近似基金會）＋無股東季度壓力」，天生具備 de Geus 四特徵中的三項（凝聚認同、財務可保守、無短期資本壓力）。它此刻最大的風險不是市場、不是使命動搖，而是「擴張期的財務槓桿」——這正是金剛組（借錢炒地）、Hudson's Bay（負債擴張）與 Steward（售後回租套現）三個失敗案例的共同死因。34 億元貸款本身不是問題，問題在於：新大樓的營運現金流能否覆蓋還本付息，以及擴張是否稀釋了那個讓它活了 70 年的核心能力與使命。",
]));

// ===== 建議 =====
children.push(H1("建議（分階段、可操作）"));
children.push(H2("第一階段｜擴張期財務防火牆——現在到新大樓啟用"));
children.push(P([
  ["1. 把 de Geus 的「財務保守」變成硬規則。", { bold: true }],
  "為新大樓設定明確的「債務／EBITDA 上限」與「現金水位下限」門檻，寫進董事會決議；一旦跌破，強制暫停非核心資本支出。判斷門檻：若新大樓啟用後兩年內營運現金流無法覆蓋 34 億元的還本付息，即為紅燈，需啟動資產或服務組合的重整，而非再借新還舊（這正是金剛組「借錢付利息」的死亡螺旋）。",
]));
children.push(P([
  ["2. 絕不做 Steward 式的售後回租套現。", { bold: true }],
  "台灣《醫療法》第 37 條已禁止財團法人為他人擔保、資金貸與董事——把這條精神擴張成內部政策：院區土地與核心不動產不得用於任何以套現為目的的金融工程。這是屏基相對於私募醫院最珍貴的結構護城河，務必守住。",
]));
children.push(H2("第二階段｜把「能力核心」講清楚——富士公式的醫院版"));
children.push(P([
  ["3. 做一次「屏基技術／能力總盤點」。", { bold: true }],
  "學富士 VISION 75 花 18 個月盤點技術的做法：列出屏基真正的可遷移能力（例如偏鄉巡迴醫療的組織能力、長照與急重症的整合、痲瘋／小兒麻痺時代累積的「弱勢與復健照護」know-how、跨文化宣教醫療的社群信任）。核心問句：屏基不是「一間有 861 床的醫院」，而是「一個精通什麼的組織」？把答案寫下來，作為所有擴張決策的篩選器。",
]));
children.push(P([
  ["4. 用鄰接市場思維規劃現址長照轉型。", { bold: true }],
  "現址轉長照，正是「核心能力（照護弱勢與慢病）→鄰接市場（高齡長照）」的富士式再應用；畢嘉士基金會的偏鄉長照與馬拉威模式，是現成的能力延伸範本。別把長照當成填空病床的副業，要當成核心能力的第二應用場。",
]));
children.push(H2("第三階段｜治理與使命制度化——長線"));
children.push(P([
  ["5. 把使命寫進薪酬與治理，而非只寫在牆上。", { bold: true }],
  "參考 Mayo「純薪水制」的精神：檢視屏基醫師薪酬是否內含過度醫療誘因；即使不能完全純薪水化，也應確保薪酬結構不與「衝量」掛鉤，讓「哪裡有需要就往哪裡去」的宗旨在制度上站得住。",
]));
children.push(P([
  ["6. 強化董事會的「使命守門人」角色與接班。", { bold: true }],
  "借鏡 Merck 家族憲章與 Mayo 理事會：明確界定董事會的責任是「理解、背書並反覆強化核心價值」，並建立董事與高階主管的接班梯隊（避免金剛組式的繼承／治理失能）。台灣醫療法已限制董事長連任與萬年董事會——把它當機會而非束縛，主動建立更新機制。",
]));
children.push(P([
  ["7. 保留「容忍邊緣試驗」的空間。", { bold: true }],
  "de Geus 四特徵中最容易被擴張期壓縮的就是「容忍邊緣的實驗」。在追求「準醫學中心」規模的同時，刻意保留小額、去中心化的創新預算（偏鄉、數位、長照、國際醫療），因為下一個「小兒麻痺矯治」級的使命突破，往往長在邊緣而非核心。",
]));

// ===== 注意事項 =====
children.push(H1("注意事項（限制與存疑）"));
children.push(P([["屏基母會考證：", { bold: true }], "本報告採用子研究查得的事實——屏基母會為「挪威協力會 / The Mission Alliance（NMA, Misjonsalliansen）」（屏基屬跨差會的美／挪／芬宣教士體系）。建議院內以自身檔案核實。"]));
children.push(P([["屏基員工總數與年營收：", { bold: true }], "可靠公開來源未查得確切數字，報告中未列出。新大樓完工時間（2026 年）為規劃／預估值，尚未確認實際啟用。"]));
children.push(P([["柯達 Sterling Drug 的財務評價有分歧：", { bold: true }], "不同來源對柯達製藥事業「淨賺或淨賠」說法不一（有稱整體小賺 14 億美元、亦有稱過程中蒸發約 5 億美元加上六年虧損）；本報告採「耗損管理注意力與資本、無綜效」的定性結論，此點證據較穩固。"]));
children.push(P([["管理故事的敘事偏誤：", { bold: true }], "柯達／富士對照常被事後包裝成過度乾淨的「英雄敘事」。富士的成功也含運氣成分（FUJITAC 偏光膜剛好碰上 LCD 爆發）；柯達的高退休金與遺留成本負擔也是破產主因之一。應把它們當「傾向性證據」而非鐵律。"]));
children.push(P([["老鋪與長壽統計的存活者偏誤：", { bold: true }], "我們看到的都是「活下來的」；同期無數家族／基金會企業也倒了。基金會結構有利長壽有實證支持，但它不是萬靈丹（Hudson's Bay 也曾多次轉型仍死）。永續的必要條件是「使命＋財務紀律＋能力再應用」三者同時在，缺一不可。"]));

// ===== 附錄 =====
children.push(H1("附錄：屏基自我檢視用的診斷性問題清單"));
const qa = [
  ["A. 能力 vs 產品（柯達／富士測試）", [
    "如果十年後「病床住院」這個產品模式大幅萎縮（如遠距醫療、居家醫療、AI 診斷興起），屏基還剩下什麼能力可以活下去？我們能說出自己的「70 項可遷移技術」嗎？",
    "我們願不願意主動「殺掉自己的金雞母」——在現有高收入科別還賺錢時，就投資會侵蝕它的新模式？",
  ]],
  ["B. 財務紀律（金剛組／Hudson's Bay／Steward 測試）", [
    "新大樓 34 億元貸款，在「入住率低於預期 20%」的壓力情境下，還本付息會不會逼我們借新還舊？我們設了紅燈門檻嗎？",
    "我們有沒有任何一筆交易，實質上是「把核心不動產變現、再回頭付租金」？（若有，立即停。）",
    "擴張後的固定成本，有多少比例是「無論病人多寡都要付」的剛性支出？這個比例安全嗎？",
  ]],
  ["C. 使命制度化（Mayo／宗教醫院測試）", [
    "「哪裡有需要就往哪裡去」的宗旨，在我們的薪酬、升遷、資源分配制度裡看得到嗎，還是只在牆上？",
    "董事會花在「守護使命」的時間，和花在「看財務報表」的時間，比例是多少？",
    "醫師的收入結構，會不會誘導他們做對醫院財務好、但對病人不必要的事？",
  ]],
  ["D. 治理與接班（Merck／金剛組測試）", [
    "十年後屏基的董事長與院長從哪裡來？我們有沒有刻意培養的接班梯隊，還是等出缺再說？",
    "我們的董事會有沒有「更新機制」，避免變成同一批人、同一種思維的萬年董事會？",
  ]],
  ["E. 容忍邊緣試驗（de Geus 測試）", [
    "屏基今年有幾個「小額、可能失敗、與主院區無關」的實驗（偏鄉、數位、長照、國際）？如果一個都沒有，我們可能已經太核心化、太保守了。",
    "上一個從「邊緣」長出來、後來變成重要使命的專案是什麼？我們還在給邊緣留空間嗎？",
  ]],
];
qa.forEach(([h, items]) => {
  children.push(H2(h));
  items.forEach(q => children.push(P(q, { num: "questions" })));
});

// back page
children.push(
  new Paragraph({ pageBreakBefore: true, children: [] }),
  ...Array.from({ length: 11 }, () => new Paragraph({ spacing: { after: 240 }, children: [] })),
  KICKER("永 續 企 業 治 理"),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: "「哪裡有需要，就往哪裡去」", font: F, size: 30, bold: true, color: NAVY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "屏東基督教醫院・1953 年創立", font: F, size: 18, color: GRAY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 80 },
    children: [new TextRun({ text: "本冊插圖與圖表為依據公開史料重繪之示意圖", font: F, size: 15, color: GRAY })],
  }),
);

// ---------------- document ----------------
const doc = new Document({
  creator: "屏東基督教醫院",
  title: "活過幾百年的企業，到底靠什麼活著、又敗在哪裡——給屏東基督教醫院的永續治理線索",
  styles: {
    default: {
      document: { run: { font: F, size: 19, color: TEXT } },
    },
  },
  numbering: {
    config: [
      {
        reference: "findings",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          style: { paragraph: { indent: { left: 340, hanging: 340 } }, run: { bold: true, color: SEPIA } },
        }],
      },
      {
        reference: "questions",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          style: { paragraph: { indent: { left: 340, hanging: 340 } }, run: { bold: true, color: SEPIA } },
        }],
      },
    ],
  },
  sections: [{
    properties: {
      titlePage: true,
      page: {
        size: { width: 8391, height: 11906 }, // A5
        margin: { top: 1080, bottom: 1021, left: 907, right: 907, header: 510, footer: 567 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: GOLD, space: 4 } },
          children: [new TextRun({ text: "永續企業治理　·　給屏東基督教醫院的線索", font: F, size: 14, color: GRAY, characterSpacing: 20 })],
        })],
      }),
      first: new Header({ children: [] }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "— ", font: F, size: 16, color: GOLD }),
            new TextRun({ children: [PageNumber.CURRENT], font: F, size: 16, color: GRAY }),
            new TextRun({ text: " —", font: F, size: 16, color: GOLD }),
          ],
        })],
      }),
      first: new Footer({ children: [] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("永續企業治理小冊子_A5.docx", buf);
  console.log("written", buf.length, "bytes");
});
