"""
Adapter registry. Add a module per chain and list it in REGISTRY.

Scope, and it is a judgement this project makes explicitly: China-origin chains,
collected market by market. The archive began with the United States and the map still reads
only US rows, but one adapter covers one market — MINISO's US and UAE estates are published by
different sites in different shapes, so they are two adapters and two chain_ids, never one.

A chain earns a place on this roster by TRADING in a market the project covers — never by being
convenient to collect. Chains with no usable locator stay here as disabled adapters carrying the
reason, so `status` shows the shape of the category rather than the shape of what happened to be
scrapable. Yang's Braised Chicken has been in America since 2017 and is the clearest case: eight
years of trading, no locator, and it would have been invisible under any other rule. Taiwanese and Hong Kong brands (Tiger Sugar, The Alley,
Gong Cha) are a different and earlier wave and are not in scope; Asian grocers such as
99 Ranch and H Mart sell Chinese products but are not Chinese chains, and including them
would answer a question nobody asked.
"""
from .base import Adapter, StoreRecord
from .mixue import MixueAdapter
from .chagee import ChageeAdapter
from .luckin import LuckinAdapter
from .miniso import MinisoAdapter
from .miniso_ae import MinisoUAEAdapter
from .haidilao_us import HaidilaoUSAdapter
from .popmart import PopMartUSAdapter
from .xiaolongkan import XiaolongkanAdapter
from .liuyishou import LiuyishouAdapter
from .aunteajenny import AunteaJennyAdapter
from .mollytea import MollyTeaAdapter
from .moge import MogeTeeAdapter
from .stubs import (HeyteaAdapter, CottiAdapter, YangsAdapter,
                    TaiErAdapter, ChaPandaAdapter, NaixueAdapter, JueweiAdapter,
                    YangguofuAdapter, FishWithYouAdapter, ZhangliangAdapter, ChahaloAdapter,
                    LelechaAdapter, NonggengjiAdapter, BaosPastryAdapter, TopToyAdapter,
                    Toys52Adapter, DezhuangAdapter, MeizhouDongpoAdapter, ShudaxiaAdapter,
                    XibeiAdapter, GrandmasHomeAdapter, XijiadeAdapter, MalubianbianAdapter,
                    FeidachuAdapter, DalongyiAdapter, ShuyiAdapter, MoreYogurtAdapter,
                    AntaAdapter, UrbanRevivoAdapter, JnbyAdapter, MeilleurMomentAdapter,
                    WallaceAdapter, ZhengxinAdapter, HiBakeAdapter)

REGISTRY: list[Adapter] = [
    MixueAdapter(),     # validated live 21 Sep 2026; 27 stores (10 open, 17 coming soon), 1 request
    ChageeAdapter(),    # validated live 21 Sep 2026; 11 stores with published coordinates, 1 request
    LuckinAdapter(),    # validated live 21 Sep 2026; 22 stores, no coordinates, 1 request
    MinisoAdapter(),    # validated live 21 Sep 2026; 462 CMS rows -> ~425 stores, 2 requests
    MinisoUAEAdapter(), # validated live 21 Sep 2026; first non-US market, 7 emirate pages
    HaidilaoUSAdapter(),# validated live 21 Sep 2026; 15 US restaurants with coordinates
    PopMartUSAdapter(), # validated live 21 Sep 2026; 182 US stores from the app API
    HeyteaAdapter(),    # blocked — see stubs.py
    CottiAdapter(),     # blocked — see stubs.py
    YangsAdapter(),     # in the US since 2017, no locator found — see stubs.py
    TaiErAdapter(),     # in the US, parent discloses counts — see stubs.py
    ChaPandaAdapter(),  # entered the US Aug 2025 — see stubs.py
    NaixueAdapter(),    # US entry reported — see stubs.py
    JueweiAdapter(),    # trades as Juewei Yabo in the US — see stubs.py
    YangguofuAdapter(), # registered US franchisor; roster from its FDD — see stubs.py
    FishWithYouAdapter(), # 鱼你在一起; found in the registry sweep — see stubs.py
    ZhangliangAdapter(), # malatang 张亮麻辣烫; 42 NA outlets claimed — see stubs.py
    ChahaloAdapter(), # premium tea 茶话弄 (Xi'an); recent US entry — see stubs.py
    LelechaAdapter(), # premium tea 乐乐茶 (Shanghai); private site — see stubs.py
    NonggengjiAdapter(), # Hunan 农耕记 (Shenzhen); Flushing + Rockville — see stubs.py
    BaosPastryAdapter(), # bakery 鲍师傅 (Beijing); Flushing — see stubs.py
    TopToyAdapter(), # art-toy TOP TOY (MINISO Group); Times Square — see stubs.py
    Toys52Adapter(), # blind-box 52TOYS (Beijing); Georgia — see stubs.py
    DezhuangAdapter(), # Chongqing hot pot 德庄; NYC + Bellevue — see stubs.py
    MeizhouDongpoAdapter(), # Sichuan 眉州东坡 (Beijing); LA since 2013 — see stubs.py
    ShudaxiaAdapter(), # Chengdu hot pot 蜀大侠 (Xiaolongkan group); Boston — see stubs.py
    XibeiAdapter(), # Northwestern 西贝莜面村; 4 SoCal outlets — see stubs.py
    GrandmasHomeAdapter(), # Hangzhou 外婆家; Manhattan — see stubs.py
    XijiadeAdapter(), # dumplings 喜家德 / Dumpling Xi; NYC — see stubs.py
    MalubianbianAdapter(), # skewer hotpot 马路边边; Orlando (churned) — see stubs.py
    FeidachuAdapter(), # Hunan 费大厨 / Chef Fei; San Diego (opened Sep 2026) — see stubs.py
    DalongyiAdapter(), # Chengdu hot pot 大龙燚; LIC + Boston — see stubs.py
    ShuyiAdapter(), # Chengdu tea 书亦烧仙草; VA + Bay Area — see stubs.py
    MoreYogurtAdapter(), # yogurt 茉酸奶 / More Yogurt; Tustin CA — see stubs.py
    AntaAdapter(), # sportswear 安踏; Beverly Hills flagship — see stubs.py
    UrbanRevivoAdapter(), # fast fashion UR; SoHo NYC flagship — see stubs.py
    JnbyAdapter(), # designer 江南布衣 / AGoodFun; SF + Seattle — see stubs.py
    MeilleurMomentAdapter(), # womenswear 伊芙丽 / Meilleur Moment; SoHo NYC — see stubs.py
    WallaceAdapter(), # fast food 华莱士 / Wallace Chicken; Walnut + West Covina CA — see stubs.py
    ZhengxinAdapter(), # fried chicken 正新鸡排 / Zhengxin Chicken Steak; CA + NYC — see stubs.py
    HiBakeAdapter(), # bakery 嗨呗可 / Hi Bake (Chengdu); Beverly Hills via Chubby Group — see stubs.py
    XiaolongkanAdapter(), # collected daily from shooloongkan.us/locations — see xiaolongkan.py
    LiuyishouAdapter(), # collected daily from liuyishouna.com per-city pages — see liuyishou.py
    AunteaJennyAdapter(), # collected daily from aunteajenny.us CMS feed — see aunteajenny.py
    MollyTeaAdapter(), # collected daily from usa.mollytea.com ASL feed (US rows) — see mollytea.py
    MogeTeeAdapter(), # collected daily from mogeteeusa.com Wix state pages (愿茶) — see moge.py
]


def by_id(chain_id: str) -> Adapter | None:
    """
    name:      by_id
    purpose:   Look an adapter up by its chain_id.
    arguments: chain_id
    returns:   Adapter or None
    effects:   None
    other:     —
    """
    return next((a for a in REGISTRY if a.chain_id == chain_id), None)
