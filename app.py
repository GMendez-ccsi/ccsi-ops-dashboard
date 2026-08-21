# TAB 5: SERVICE HOURS PER CAMPAIGN
with tab_service_hours:
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.subheader("⏱️ Service Hours & Facturabilidad per Campaign")
    with head_col2:
        st.markdown("[🔗 Open Live Service Hours Sheet](https://docs.google.com/spreadsheets/d/1PEybVFo8uL4jfasxJfrvWtEFHyk1EYGmsjLnMgk1Qt4/edit#gid=1459025310)")

    months = ["Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26", "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"]
    
    # Complete dataset including FTE, Target, Accrued, %, and MoM
    data_matrix = {
        "Month": months,
        # CDMX Metrics
        "CDMX_FTE": [32, 32, 31, 30, 31, 31, 31, 31, 31, 31, 31, 31],
        "CDMX_Target": [6678.5, 6080.0, 6526.0, 6374.5, 6222.5, 6080.0, 6051.5, 5652.5, 5529.0, 5652.5, 5491.0, 5747.5],
        "CDMX_Accrued": [5330.338, 5673.986, 5986.862, 5475.0, 5768.27, 5617.34, 5626.0, 5500.0, 0.0, 0.0, 0.0, 0.0],
        "CDMX_Pct": [79.81, 93.32, 91.74, 85.89, 92.70, 92.39, 92.97, 97.30, 0.0, 0.0, 0.0, 0.0],
        "CDMX_MoM": [None, 13.51, -1.58, -5.85, 6.81, -0.31, 0.58, 4.33, None, None, None, None],
        
        # TJ Metrics
        "TJ_FTE": [7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6],
        "TJ_Target": [1463.0, 1330.0, 1463.0, 1463.0, 1206.5, 1244.5, 1292.0, 1216.0, 1254.0, 1244.5, 1206.5, 1311.0],
        "TJ_Accrued": [1335.85, 1228.586, 1307.67, 1358.5, 1095.53, 1084.25, 907.6, 1004.0, 0.0, 0.0, 0.0, 0.0],
        "TJ_Pct": [91.31, 92.37, 89.38, 92.86, 90.80, 87.12, 70.25, 82.57, 0.0, 0.0, 0.0, 0.0],
        "TJ_MoM": [None, 1.07, -2.99, 3.47, -2.05, -3.68, -16.88, 12.32, None, None, None, None],
    }

    # Plotly Chart Generator
    def create_site_chart(site_name, target_vals, accrued_vals, pct_vals):
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Target Hours Bar
        fig.add_trace(
            go.Bar(
                x=months, 
                y=target_vals, 
                name="Target Hours", 
                marker_color="#4B9CD3",
                text=[f"{v:g}" for v in target_vals],
                textposition="auto"
            ),
            secondary_y=False,
        )

        # Accrued Hours Bar
        fig.add_trace(
            go.Bar(
                x=months, 
                y=accrued_vals, 
                name="Accrued", 
                marker_color="#52B788",
                text=[f"{v:g}" if v > 0 else "0" for v in accrued_vals],
                textposition="auto"
            ),
            secondary_y=False,
        )

        # % Line Trace
        fig.add_trace(
            go.Scatter(
                x=months, 
                y=pct_vals, 
                name="%", 
                mode="lines+markers+text",
                line=dict(color="#FF9F1C", width=2, dash="dash"),
                marker=dict(symbol="star", size=9, color="#FF9F1C"),
                text=[f"{v:.2f}%" if v > 0 else "" for v in pct_vals],
                textposition="top center",
                textfont=dict(color="#FF9F1C", size=11)
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title=dict(text=f"<b>{site_name} Performance</b>", font=dict(size=18, color="#333")),
            barmode="group",
            bargap=0.2,
            bargroupgap=0.05,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=50, b=20),
            height=350,
            paper_bgcolor="white",
            plot_bgcolor="#F9F9F9"
        )

        fig.update_yaxes(title_text="", secondary_y=False, showgrid=True, gridcolor="#E5E5E5")
        fig.update_yaxes(title_text="", secondary_y=True, range=[0, 125], showgrid=False, ticksuffix="%")
        
        return fig

    # 1. Render Dual-Axis Charts
    st.plotly_chart(create_site_chart("TJ", data_matrix["TJ_Target"], data_matrix["TJ_Accrued"], data_matrix["TJ_Pct"]), use_container_width=True)
    st.plotly_chart(create_site_chart("CDMX", data_matrix["CDMX_Target"], data_matrix["CDMX_Accrued"], data_matrix["CDMX_Pct"]), use_container_width=True)

    st.divider()

    # 2. Month-over-Month Data Table
    st.markdown("### 📈 Month over Month (MoM) Trend & Performance Summary")
    
    # Format DataFrame for UI
    df_mom = pd.DataFrame({
        "CDMX Month": data_matrix["Month"],
        "CDMX FTE": data_matrix["CDMX_FTE"],
        "CDMX Target": data_matrix["CDMX_Target"],
        "CDMX Accrued": data_matrix["CDMX_Accrued"],
        "CDMX %": [f"{v:.2f}%" for v in data_matrix["CDMX_Pct"]],
        "CDMX MoM": [f"{v:+.2f}%" if v is not None else "" for v in data_matrix["CDMX_MoM"]],
        "TJ Month": data_matrix["Month"],
        "TJ FTE": data_matrix["TJ_FTE"],
        "TJ Target": data_matrix["TJ_Target"],
        "TJ Accrued": data_matrix["TJ_Accrued"],
        "TJ %": [f"{v:.2f}%" for v in data_matrix["TJ_Pct"]],
        "TJ MoM": [f"{v:+.2f}%" if v is not None else "" for v in data_matrix["TJ_MoM"]],
    })

    st.dataframe(df_mom, use_container_width=True, hide_index=True)
