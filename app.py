"""Streamlit interface for analytics, ingestion operations, and grounded Q&A."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from eci.config import get_settings
from eci.health import collect_health
from eci.schemas import SearchFilters
from eci.security import SessionRateLimiter
from eci.services import build_services

st.set_page_config(
    page_title="Enterprise Complaint Intelligence",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def get_services():
    return build_services(get_settings())


@st.cache_resource
def get_rate_limiter():
    settings = get_settings()
    return SessionRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)


@st.cache_data(ttl=5)
def load_complaints() -> pd.DataFrame:
    return get_services().database.complaints_dataframe()


@st.cache_data(ttl=5)
def load_runs() -> pd.DataFrame:
    return get_services().database.ingestion_runs_dataframe()


@st.cache_data(ttl=5)
def load_rejections() -> pd.DataFrame:
    return get_services().database.rejected_records_dataframe()


services = get_services()
settings = services.settings
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.title("Enterprise Complaint Intelligence Platform")
st.caption(
    "Structured analytics over validated relational data, plus source-grounded retrieval over complaint narratives."
)

with st.sidebar:
    st.header("Runtime")
    st.write(f"**Database:** `{settings.database_dialect}`")
    st.write(f"**Vector store:** `{settings.vector_backend}`")
    st.write(f"**Embeddings:** `{services.embeddings.model_name}`")
    st.write(f"**Answer mode:** `{services.answers.model_name}`")
    st.divider()
    st.subheader("Health")
    for health in collect_health(services):
        icon = "✅" if health.healthy else "❌"
        st.write(f"{icon} **{health.component}**")
        st.caption(health.detail)

pages = st.tabs(
    ["Executive Dashboard", "Cognitive Bot", "Ingest Data", "Data Quality & Operations", "Architecture & Learn"]
)

with pages[0]:
    frame = load_complaints()
    if frame.empty:
        st.info("No records are loaded. Run the portable bootstrap or use the Ingest Data tab.")
    else:
        frame["date_received"] = pd.to_datetime(frame["date_received"])
        col_a, col_b, col_c = st.columns(3)
        products = sorted(frame["product"].dropna().unique().tolist())
        states = sorted(frame["state"].dropna().unique().tolist())
        companies = sorted(frame["company"].dropna().unique().tolist())
        selected_products = col_a.multiselect("Product", products)
        selected_states = col_b.multiselect("State", states)
        selected_companies = col_c.multiselect("Company", companies)

        filtered = frame.copy()
        if selected_products:
            filtered = filtered[filtered["product"].isin(selected_products)]
        if selected_states:
            filtered = filtered[filtered["state"].isin(selected_states)]
        if selected_companies:
            filtered = filtered[filtered["company"].isin(selected_companies)]

        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        metric_a.metric("Complaints", f"{len(filtered):,}")
        timely_rate = filtered["timely_response"].mean() * 100 if len(filtered) else 0
        metric_b.metric("Timely response", f"{timely_rate:.1f}%")
        disputed = pd.to_numeric(filtered["amount_disputed"], errors="coerce").sum()
        metric_c.metric("Disputed amount", f"${disputed:,.2f}")
        metric_d.metric("Companies", f"{filtered['company'].nunique():,}")

        left, right = st.columns(2)
        monthly = (
            filtered.assign(month=filtered["date_received"].dt.to_period("M").dt.to_timestamp())
            .groupby("month")["complaint_id"]
            .count()
            .rename("complaints")
        )
        left.subheader("Complaints over time")
        left.line_chart(monthly)

        by_product = filtered.groupby("product")["complaint_id"].count().sort_values(ascending=False)
        right.subheader("Complaints by product")
        right.bar_chart(by_product)

        st.subheader("Complaint records")
        st.dataframe(
            filtered[
                [
                    "complaint_id",
                    "date_received",
                    "product",
                    "issue",
                    "company",
                    "state",
                    "status",
                    "timely_response",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

with pages[1]:
    st.subheader("Ask the complaint evidence")
    st.write(
        "Every response is produced from retrieved complaint records and displays the source IDs used."
    )
    frame = load_complaints()
    product_options = [""] + sorted(frame["product"].dropna().unique().tolist()) if not frame.empty else [""]
    state_options = [""] + sorted(frame["state"].dropna().unique().tolist()) if not frame.empty else [""]
    company_options = [""] + sorted(frame["company"].dropna().unique().tolist()) if not frame.empty else [""]

    with st.form("question_form"):
        query = st.text_area(
            "Question",
            value="What complaints describe a lien release or vehicle title arriving late?",
            max_chars=settings.max_query_characters,
        )
        f1, f2, f3, f4 = st.columns(4)
        product = f1.selectbox("Product filter", product_options)
        state = f2.selectbox("State filter", state_options)
        company = f3.selectbox("Company filter", company_options)
        top_k = f4.slider("Retrieved records", 1, settings.max_top_k, settings.default_top_k)
        submitted = st.form_submit_button("Retrieve and answer", type="primary")

    if submitted:
        limiter = get_rate_limiter()
        if not limiter.allow(st.session_state.session_id):
            st.error("Too many requests in a short period. Pause briefly before trying again.")
        else:
            try:
                with st.spinner("Retrieving evidence and preparing a grounded answer..."):
                    result = services.rag.ask(
                        query,
                        top_k=top_k,
                        filters=SearchFilters(
                            product=product or None,
                            state=state or None,
                            company=company or None,
                        ),
                    )
                st.markdown(result.answer)
                st.caption(
                    f"Answer provider: {result.model_name} | Retrieved sources: {result.retrieval_count}"
                )
                st.subheader("Retrieved evidence")
                for source in result.sources:
                    label = (
                        f"{source.complaint_id} — {source.metadata.get('product')} — "
                        f"score {source.score:.3f}"
                    )
                    with st.expander(label):
                        st.write(source.text)
                        st.json(source.metadata)
            except Exception as exc:
                st.error(f"The request failed safely: {type(exc).__name__}: {exc}")

with pages[2]:
    st.subheader("Run the validated ingestion pipeline")
    st.warning("Use public, synthetic, or formally approved data. Do not upload confidential production records.")
    upload = st.file_uploader("CSV file", type=["csv"])
    if upload is not None:
        st.write(f"Selected: **{Path(upload.name).name}** ({upload.size:,} bytes)")
        if st.button("Run complete pipeline", type="primary"):
            safe_name = Path(upload.name).name
            target = settings.raw_data_dir / f"upload_{uuid.uuid4().hex[:8]}_{safe_name}"
            try:
                target.write_bytes(upload.getbuffer())
                with st.spinner("Cleaning, validating, loading SQL, embedding, and indexing..."):
                    summary = services.pipeline.run(target)
                st.success(f"Pipeline finished with status {summary.status.value}.")
                st.json(summary.model_dump(mode="json"))
                load_complaints.clear()
                load_runs.clear()
                load_rejections.clear()
            except Exception as exc:
                st.error(f"Ingestion failed safely: {type(exc).__name__}: {exc}")

with pages[3]:
    st.subheader("Ingestion audit trail")
    runs = load_runs()
    if runs.empty:
        st.info("No ingestion runs have been recorded.")
    else:
        st.dataframe(runs, use_container_width=True, hide_index=True)

    st.subheader("Rejected-record quarantine")
    rejections = load_rejections()
    if rejections.empty:
        st.success("No rejected records are currently stored.")
    else:
        st.dataframe(rejections, use_container_width=True, hide_index=True)
        st.download_button(
            "Download rejection report",
            data=rejections.to_csv(index=False).encode("utf-8"),
            file_name="rejected_records.csv",
            mime="text/csv",
        )

with pages[4]:
    st.subheader("How the system works")
    st.code(
        """RAW CSV
   │
   ▼
Pandas cleaning and normalization
   │
   ▼
Pydantic validation ───── invalid rows ─────► quarantine + audit
   │
   ▼
Validated, PII-redacted records
   ├────────► SQL system of record ─────────► Power BI / dashboard
   │
   └────────► embeddings ─► vector index ─► retrieval ─► grounded answer
""",
        language="text",
    )
    st.markdown(
        """
**What to inspect while learning**

1. `src/eci/cleaning.py` standardizes messy source values but does not conceal invalid records.
2. `src/eci/schemas.py` declares the formal data contract.
3. `src/eci/pipeline.py` coordinates the two destinations and writes audit outputs.
4. `src/eci/database.py` owns transactional relational persistence.
5. `src/eci/vector_store.py` lets the same application use a local index or Weaviate.
6. `src/eci/rag.py` performs retrieval before any answer is generated.

The local profile is intentionally dependency-light. Switching environment values activates MySQL, Weaviate, and OpenAI without changing business logic.
"""
    )
