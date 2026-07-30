import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

# ------------------------------------------------------------
# 기본 화면 설정
# ------------------------------------------------------------
st.set_page_config(page_title="전국 고령화 지도", layout="wide")
st.title("🗺️ 전국 시군구 고령화 지도")
st.caption("시군구별 65세 이상 인구 비율(고령화율)을 색으로 나타낸 단계구분도입니다.")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


# ------------------------------------------------------------
# 데이터 불러오기 (한 번 불러온 뒤에는 캐시에 저장해서 재사용)
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_population():
    # '코드' 열은 계산용 숫자가 아니라 이름표이므로 문자열(str)로 읽어야
    # 앞자리 0이 사라지지 않습니다.
    df = pd.read_csv(POP_URL, compression="gzip", dtype={"코드": str})
    return df


@st.cache_data(show_spinner=False)
def load_geojson():
    res = requests.get(GEO_URL)
    res.raise_for_status()
    return res.json()


with st.spinner("데이터를 불러오는 중입니다... 처음 실행 시 시간이 조금 걸릴 수 있어요."):
    df = load_population()
    geojson = load_geojson()

# 혹시 앞자리 0이 빠진 경우를 대비해 10자리로 맞춰줍니다.
df["코드"] = df["코드"].astype(str).str.zfill(10)
# '코드' 앞 5자리 = 시군구 코드
df["시군구코드"] = df["코드"].str[:5]

# ------------------------------------------------------------
# 나이별 열 이름 정리하기
# 예: '계_0세' -> 0,  '계_100세 이상' -> 100
# ------------------------------------------------------------
def age_to_num(col_name: str) -> int:
    text = col_name.replace("계_", "").replace("세 이상", "").replace("세", "")
    return int(text)


age_cols_total = [c for c in df.columns if c.startswith("계_")]  # 계(남+여) 열만 사용

old_cols = [c for c in age_cols_total if age_to_num(c) >= 65]      # 65세 이상
young_cols = [c for c in age_cols_total if age_to_num(c) <= 14]    # 0~14세 (유소년인구)
work_cols = [c for c in age_cols_total if 15 <= age_to_num(c) <= 64]  # 15~64세 (생산연령인구)

df["총인구"] = df[age_cols_total].sum(axis=1)
df["고령인구"] = df[old_cols].sum(axis=1)

# ------------------------------------------------------------
# 가장 최신 연도만 골라서 지도 그리기
# ------------------------------------------------------------
latest_year = int(df["연도"].max())
df_latest = df[df["연도"] == latest_year].copy()

# 읍·면·동 단위 인구를 시군구 단위로 합치기
grouped = (
    df_latest.groupby(["시군구코드", "시도", "시군구"], as_index=False)[["총인구", "고령인구"]]
    .sum()
)
grouped["고령화율"] = grouped["고령인구"] / grouped["총인구"] * 100
grouped["시군구코드"] = grouped["시군구코드"].str.zfill(5)

# ------------------------------------------------------------
# 색을 5단계로 끊기 (19% / 23% / 28% / 38% 기준)
# ------------------------------------------------------------
bins = [-np.inf, 19, 23, 28, 38, np.inf]
labels = ["19% 미만", "19%~23%", "23%~28%", "28%~38%", "38% 이상"]
grouped["구간"] = pd.cut(grouped["고령화율"], bins=bins, labels=labels, right=False)

# 옅은 색 -> 진한 색 순서로 5가지 색 지정
colors = ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]
color_map = dict(zip(labels, colors))

# ------------------------------------------------------------
# 단계구분도 그리기 (배경 타일 없이 경계선만 표시)
# ------------------------------------------------------------
fig = px.choropleth(
    grouped,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="구간",
    category_orders={"구간": labels},
    color_discrete_map=color_map,
    hover_name="시군구",
    hover_data={
        "시도": True,
        "고령화율": ":.1f",
        "시군구코드": False,
        "구간": False,
    },
    labels={"구간": "고령화율 구간", "고령화율": "고령화율(%)", "시도": "시도"},
)

# 배경 지도(타일) 없이 시군구 경계선만 보이게 설정
fig.update_geos(visible=False, fitbounds="locations")
fig.update_traces(marker_line_width=0.5, marker_line_color="white")
fig.update_layout(
    title=f"{latest_year}년 시군구별 65세 이상 인구 비율",
    legend_title_text="고령화율 구간",
    margin={"r": 0, "t": 50, "l": 0, "b": 0},
    height=700,
)

st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# 연령대별 인구 비율 변화 추이 (전국 기준, 연도별)
# ------------------------------------------------------------
st.subheader("📈 연도별 연령대 인구 비율 변화 (전국)")
st.caption(
    "요청하신 연령 구간 표기가 명확하지 않아, 인구통계에서 흔히 쓰는 "
    "'0~14세(유소년인구)'와 '15~64세(생산연령인구)' 두 구간의 비율 변화로 표를 만들었습니다. "
    "다른 연령 구간을 원하시면 말씀해 주세요."
)

df["유소년인구"] = df[young_cols].sum(axis=1)
df["생산연령인구"] = df[work_cols].sum(axis=1)

yearly = df.groupby("연도", as_index=False)[["총인구", "유소년인구", "생산연령인구"]].sum()
yearly["유소년인구비율(%)"] = (yearly["유소년인구"] / yearly["총인구"] * 100).round(2)
yearly["생산연령인구비율(%)"] = (yearly["생산연령인구"] / yearly["총인구"] * 100).round(2)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**0~14세 (유소년인구) 비율 추이**")
    st.dataframe(
        yearly[["연도", "유소년인구비율(%)"]],
        use_container_width=True,
        hide_index=True,
    )

with col2:
    st.markdown("**15~64세 (생산연령인구) 비율 추이**")
    st.dataframe(
        yearly[["연도", "생산연령인구비율(%)"]],
        use_container_width=True,
        hide_index=True,
    )
