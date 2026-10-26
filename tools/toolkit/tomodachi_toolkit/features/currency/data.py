"""Currency symbols and names (pure data)."""


SYMBOL = {}


for codes, spec in (
        ('USD AUD CAD HKD NZD SGD TWD ARS BSD BBD BMD BZD BND CLP COP CUP DOP FJD GYD JMD KYD LRD MXN NAD SBD SRD TTD TVD UYU XCD ZWL TOP KID', ('$', 0x24, None, 0)),
        ('GBP EGP FKP GIP SHP GGP IMP JEP LBP SYP SSP SDG', ('£', 0xA3, 'L', 1)),
        ('JPY CNY CNH', ('¥', 0xFFE5, None, 0)),
        ('EUR', ('€', 0x20AC, 'C', 2)),
        ('ANG AWG XCG', ('ƒ', 0x192, 'f', 0)),
        ('KRW', ('₩', None, 'W', 2)),
        ('INR', ('₹', None, 'R', 2)),
        ('RUB', ('₽', None, 'P', 2)),
        ('PHP', ('₱', None, 'P', 2)),
        ('TRY', ('₺', None, 'L', 2)),
        ('VND', ('₫', None, 'D', 2)),
        ('NGN', ('₦', None, 'N', 2)),
        ('KZT', ('₸', None, 'T', 1)),
        ('MNT', ('₮', None, 'T', 2)),
        ('GHS', ('₵', None, 'C', 1)),
        ('CRC', ('₡', None, 'C', 2)),
        ('PYG', ('₲', None, 'G', 2)),
        ('LAK', ('₭', None, 'K', 2)),
        ('AZN', ('₼', None, 'M', 1)),
        ('GEL', ('₾', None, 'L', 2)),
        ('ILS', ('₪', None, 'I', 2)),
        ('UAH', ('₴', None, 'H', 2)),
        ('DKK FOK HRK ISK NOK SEK', ('k', None, 'k', 0)),
        ('PLN', ('z', None, 'z', 0)),
        ('AED DZD IQD MKD RSD TND STN GMD MAD AMD', ('D', None, 'D', 0)),
        ('ALL BGN HNL LSL SZL MDL RON LYD SLE SLL', ('L', None, 'L', 0)),
        ('AOA BAM CZK KES KWD MMK MWK PGK ZMW', ('K', None, 'K', 0)),
        ('BIF CDF CHF DJF GNF HUF KMF RWF XAF XOF XPF', ('F', None, 'F', 0)),
        ('KGS PEN SAR SOS TJS UZS XDR', ('S', None, 'S', 0)),
        ('BRL IDR IRR KHR LKR MUR MVR MYR NPR OMR PKR SCR YER ZAR', ('R', None, 'R', 0)),
        ('BOB BYN ETB PAB VES THB BHD', ('B', None, 'B', 0)),
        ('NIO', ('C', None, 'C', 0)),
        ('CVE', ('E', None, 'E', 0)),
        ('HTG', ('G', None, 'G', 0)),
        ('GTQ QAR', ('Q', None, 'Q', 0)),
        ('BTN ERN', ('N', None, 'N', 0)),
        ('MZN', ('M', None, 'M', 0)),
        ('BWP MOP', ('P', None, 'P', 0)),
        ('AFN MGA', ('A', None, 'A', 0)),
        ('CLF MRU UGX', ('U', None, 'U', 0)),
        ('BDT TMT TZS WST', ('T', None, 'T', 0)),
        ('VUV', ('V', None, 'V', 0)),
        ('ZWG', ('Z', None, 'Z', 0)),
        ('JOD', ('J', None, 'J', 0)),
):
    for code in codes.split():
        SYMBOL[code] = spec


NAMES = dict(line.split(' ', 1) for line in '''
AED UAE Dirham
AFN Afghan Afghani
ALL Albanian Lek
AMD Armenian Dram
ANG Netherlands Antillean Guilder
AOA Angolan Kwanza
ARS Argentine Peso
AUD Australian Dollar
AWG Aruban Florin
AZN Azerbaijani Manat
BAM Bosnia-Herzegovina Mark
BBD Barbadian Dollar
BDT Bangladeshi Taka
BGN Bulgarian Lev
BHD Bahraini Dinar
BIF Burundian Franc
BMD Bermudan Dollar
BND Brunei Dollar
BOB Bolivian Boliviano
BRL Brazilian Real
BSD Bahamian Dollar
BTN Bhutanese Ngultrum
BWP Botswanan Pula
BYN Belarusian Ruble
BZD Belize Dollar
CAD Canadian Dollar
CDF Congolese Franc
CHF Swiss Franc
CLF Chilean Unit of Account
CLP Chilean Peso
CNH Chinese Yuan (offshore)
CNY Chinese Yuan
COP Colombian Peso
CRC Costa Rican Colón
CUP Cuban Peso
CVE Cape Verdean Escudo
CZK Czech Koruna
DJF Djiboutian Franc
DKK Danish Krone
DOP Dominican Peso
DZD Algerian Dinar
EGP Egyptian Pound
ERN Eritrean Nakfa
ETB Ethiopian Birr
EUR Euro
FJD Fijian Dollar
FKP Falkland Islands Pound
FOK Faroese Króna
GBP British Pound
GEL Georgian Lari
GGP Guernsey Pound
GHS Ghanaian Cedi
GIP Gibraltar Pound
GMD Gambian Dalasi
GNF Guinean Franc
GTQ Guatemalan Quetzal
GYD Guyanese Dollar
HKD Hong Kong Dollar
HNL Honduran Lempira
HRK Croatian Kuna
HTG Haitian Gourde
HUF Hungarian Forint
IDR Indonesian Rupiah
ILS Israeli New Shekel
IMP Manx Pound
INR Indian Rupee
IQD Iraqi Dinar
IRR Iranian Rial
ISK Icelandic Króna
JEP Jersey Pound
JMD Jamaican Dollar
JOD Jordanian Dinar
JPY Japanese Yen
KES Kenyan Shilling
KGS Kyrgyzstani Som
KHR Cambodian Riel
KID Kiribati Dollar
KMF Comorian Franc
KRW South Korean Won
KWD Kuwaiti Dinar
KYD Cayman Islands Dollar
KZT Kazakhstani Tenge
LAK Lao Kip
LBP Lebanese Pound
LKR Sri Lankan Rupee
LRD Liberian Dollar
LSL Lesotho Loti
LYD Libyan Dinar
MAD Moroccan Dirham
MDL Moldovan Leu
MGA Malagasy Ariary
MKD Macedonian Denar
MMK Myanmar Kyat
MNT Mongolian Tugrik
MOP Macanese Pataca
MRU Mauritanian Ouguiya
MUR Mauritian Rupee
MVR Maldivian Rufiyaa
MWK Malawian Kwacha
MXN Mexican Peso
MYR Malaysian Ringgit
MZN Mozambican Metical
NAD Namibian Dollar
NGN Nigerian Naira
NIO Nicaraguan Córdoba
NOK Norwegian Krone
NPR Nepalese Rupee
NZD New Zealand Dollar
OMR Omani Rial
PAB Panamanian Balboa
PEN Peruvian Sol
PGK Papua New Guinean Kina
PHP Philippine Peso
PKR Pakistani Rupee
PLN Polish Złoty
PYG Paraguayan Guaraní
QAR Qatari Riyal
RON Romanian Leu
RSD Serbian Dinar
RUB Russian Ruble
RWF Rwandan Franc
SAR Saudi Riyal
SBD Solomon Islands Dollar
SCR Seychellois Rupee
SDG Sudanese Pound
SEK Swedish Krona
SGD Singapore Dollar
SHP Saint Helena Pound
SLE Sierra Leonean Leone
SLL Sierra Leonean Leone (old)
SOS Somali Shilling
SRD Surinamese Dollar
SSP South Sudanese Pound
STN São Tomé and Príncipe Dobra
SYP Syrian Pound
SZL Swazi Lilangeni
THB Thai Baht
TJS Tajikistani Somoni
TMT Turkmenistani Manat
TND Tunisian Dinar
TOP Tongan Paʻanga
TRY Turkish Lira
TTD Trinidad and Tobago Dollar
TVD Tuvaluan Dollar
TWD New Taiwan Dollar
TZS Tanzanian Shilling
UAH Ukrainian Hryvnia
UGX Ugandan Shilling
USD US Dollar
UYU Uruguayan Peso
UZS Uzbekistani Som
VES Venezuelan Bolívar
VND Vietnamese Dong
VUV Vanuatu Vatu
WST Samoan Tala
XAF Central African CFA Franc
XCD East Caribbean Dollar
XCG Caribbean Guilder
XDR Special Drawing Rights
XOF West African CFA Franc
XPF CFP Franc
YER Yemeni Rial
ZAR South African Rand
ZMW Zambian Kwacha
ZWG Zimbabwe Gold
ZWL Zimbabwean Dollar
'''.strip().splitlines())
