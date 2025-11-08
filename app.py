import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

st.set_page_config(page_title="交互式绘图工具", layout="wide")

# 初始化session state
if 'charts' not in st.session_state:
    st.session_state.charts = []
if 'data' not in st.session_state:
    st.session_state.data = None
if 'filename' not in st.session_state:
    st.session_state.filename = None

def load_data(uploaded_file):
    """加载CSV或Excel文件"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("不支持的文件格式，请上传CSV或Excel文件")
            return None
        return df
    except Exception as e:
        st.error(f"读取文件出错: {str(e)}")
        return None

def create_plotly_chart(chart_config, data):
    """根据配置创建Plotly图表"""
    
    # 判断是否有双y轴
    y1_columns = chart_config['y1_columns']
    y2_columns = chart_config['y2_columns']
    has_dual_axis = len(y2_columns) > 0
    
    # 获取小数位数设置
    decimal_places = chart_config.get('decimal_places', 4)
    
    # 根据小数位数生成格式字符串
    if decimal_places == 0:
        hover_format = ':.0f'
        tick_format = ',.0f'
    else:
        hover_format = f':.{decimal_places}f'
        tick_format = f',.{decimal_places}f'
    
    # 创建图表
    fig = go.Figure()
    
    # 添加Y1轴的曲线
    for y_col in y1_columns:
        if y_col not in data.columns:
            continue
            
        x_data = data[chart_config['x_column']]
        y_data = data[y_col]
        
        if chart_config['chart_type'] == '折线图':
            trace = go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_col,
                yaxis='y',
                hovertemplate=f'<b>{y_col}</b>: %{{y{hover_format}}}<extra></extra>'
            )
        else:  # 散点图 - 使用Scattergl提升性能
            trace = go.Scattergl(
                x=x_data,
                y=y_data,
                mode='markers',
                name=y_col,
                yaxis='y',
                hovertemplate=f'<b>{y_col}</b>: %{{y{hover_format}}}<extra></extra>'
            )
        
        fig.add_trace(trace)
    
    # 添加Y2轴的曲线
    for y_col in y2_columns:
        if y_col not in data.columns:
            continue
            
        x_data = data[chart_config['x_column']]
        y_data = data[y_col]
        
        if chart_config['chart_type'] == '折线图':
            trace = go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_col,
                yaxis='y2',
                hovertemplate=f'<b>{y_col}</b>: %{{y{hover_format}}}<extra></extra>'
            )
        else:  # 散点图 - 使用Scattergl提升性能
            trace = go.Scattergl(
                x=x_data,
                y=y_data,
                mode='markers',
                name=y_col,
                yaxis='y2',
                hovertemplate=f'<b>{y_col}</b>: %{{y{hover_format}}}<extra></extra>'
            )
        
        fig.add_trace(trace)
    
    # Y1轴标题
    y1_title = y1_columns[0] if len(y1_columns) > 0 else 'Y1轴'
    
    # 设置布局
    layout_config = {
        'title': chart_config['title'],
        'xaxis': {
            'title': chart_config['x_column'],
            'showgrid': chart_config['show_grid'],
            'showline': True,
            'zeroline': True,
            'fixedrange': False,
            'exponentformat': 'none',  # 不使用科学计数法
            'separatethousands': True   # 千位分隔符
        },
        'yaxis': {
            'title': y1_title,
            'showgrid': chart_config['show_grid'],
            'showline': True,
            'zeroline': True,
            'fixedrange': False,
            'exponentformat': 'none',  # 不使用科学计数法
            'tickformat': tick_format   # 设置刻度格式
        },
        'hovermode': 'x unified',  # 显示所有曲线的值，带纵向虚线
        'height': chart_config['height'],
        'showlegend': True,
        'legend': {
            'orientation': 'v',
            'yanchor': 'top',
            'y': 1,
            'xanchor': 'left',
            'x': 1.02
        },
        'dragmode': 'zoom'  # 支持缩放模式
    }
    
    # 如果有双y轴
    if has_dual_axis:
        y2_title = y2_columns[0] if len(y2_columns) > 0 else 'Y2轴'
        layout_config['yaxis2'] = {
            'title': y2_title,
            'showgrid': False,
            'overlaying': 'y',
            'side': 'right',
            'showline': True,
            'zeroline': True,
            'fixedrange': False,
            'exponentformat': 'none',  # 不使用科学计数法
            'tickformat': tick_format   # 设置刻度格式
        }
    
    fig.update_layout(**layout_config)
    
    # 启用滚轮缩放（在拖动轴时也可以使用滚轮）
    config = {
        'scrollZoom': True,  # 启用滚轮缩放
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToAdd': ['drawopenpath', 'eraseshape']
    }
    
    return fig, config

# 主标题
st.title("📊 交互式绘图工具")
st.markdown("---")

# 侧边栏：文件上传
with st.sidebar:
    st.header("📁 数据加载")
    uploaded_file = st.file_uploader(
        "上传CSV或Excel文件",
        type=['csv', 'xlsx', 'xls'],
        help="选择一个数据文件，第一行应为列名"
    )
    
    if uploaded_file is not None:
        if st.session_state.filename != uploaded_file.name:
            st.session_state.data = load_data(uploaded_file)
            st.session_state.filename = uploaded_file.name
            st.session_state.charts = []  # 清空之前的图表
        
        if st.session_state.data is not None:
            st.success(f"✅ 已加载: {uploaded_file.name}")
            st.info(f"数据形状: {st.session_state.data.shape[0]} 行 × {st.session_state.data.shape[1]} 列")
            
            # 显示数据预览
            with st.expander("📋 数据预览"):
                st.dataframe(st.session_state.data.head(10), use_container_width=True)

# 主界面
if st.session_state.data is not None:
    data = st.session_state.data
    columns = data.columns.tolist()
    
    # 创建新图表区域
    st.header("➕ 创建新图表")
    
    with st.form("new_chart_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            chart_title = st.text_input("图表标题", value=f"图表 {len(st.session_state.charts) + 1}")
            chart_type = st.selectbox("图表类型", ['折线图', '散点图'])
            x_column = st.selectbox("X轴 (横坐标)", columns)
            y1_columns = st.multiselect(
                "Y1轴 (左侧纵坐标)", 
                columns,
                help="可以选择多个列显示在左侧Y轴"
            )
        
        with col2:
            chart_height = st.slider("图表高度 (像素)", 300, 800, 500, 50)
            show_grid = st.checkbox("显示网格", value=True)
            decimal_places = st.selectbox(
                "数值小数位数",
                options=[0, 1, 2, 3, 4, 5, 6],
                index=4,
                help="控制悬浮框和坐标轴刻度显示的小数位数"
            )
            y2_columns = st.multiselect(
                "Y2轴 (右侧纵坐标)", 
                columns,
                help="可选，选择后将在右侧显示独立的Y轴"
            )
        
        submitted = st.form_submit_button("🎨 生成图表", use_container_width=True)
        
        if submitted:
            if not y1_columns and not y2_columns:
                st.error("请至少为Y1轴或Y2轴选择一个列！")
            else:
                chart_config = {
                    'title': chart_title,
                    'chart_type': chart_type,
                    'x_column': x_column,
                    'y1_columns': y1_columns,
                    'y2_columns': y2_columns,
                    'show_grid': show_grid,
                    'height': chart_height,
                    'decimal_places': decimal_places
                }
                st.session_state.charts.append(chart_config)
                st.success("✅ 图表已添加！")
                st.rerun()
    
    st.markdown("---")
    
    # 显示所有图表
    if st.session_state.charts:
        st.header("📈 图表显示区域")
        
        for idx, chart_config in enumerate(st.session_state.charts):
            with st.container():
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.subheader(f"{idx + 1}. {chart_config['title']}")
                with col2:
                    if st.button("🗑️ 删除", key=f"delete_{idx}"):
                        st.session_state.charts.pop(idx)
                        st.rerun()
                
                try:
                    fig, config = create_plotly_chart(chart_config, data)
                    st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart_{idx}")
                except Exception as e:
                    st.error(f"绘制图表出错: {str(e)}")
                
                st.markdown("---")
        
        # 清空所有图表按钮
        if st.button("🗑️ 清空所有图表", type="secondary"):
            st.session_state.charts = []
            st.rerun()
    else:
        st.info("👆 请在上方创建新图表")
        
else:
    # 未加载数据时的提示
    st.info("👈 请在左侧上传CSV或Excel文件开始使用")
    
    # 显示使用说明
    st.markdown("""
    ## 📖 使用说明
    
    ### 功能特点
    - ✅ 支持CSV和Excel文件格式
    - ✅ 交互式折线图和散点图
    - ✅ 自由选择X轴和多个Y轴列
    - ✅ 独立的Y1轴（左侧）和Y2轴（右侧）
    - ✅ 可选显示网格
    - ✅ 纵向虚线联动显示所有曲线的值
    - ✅ 完整数值显示，可控制小数位数
    - ✅ 图表可缩放、平移
    - ✅ 滚轮缩放Y轴范围（鼠标悬停在Y轴上时）
    - ✅ WebGL加速散点图，支持大数据量流畅渲染
    - ✅ 在一个页面创建多个图表
    - ✅ 自适应尺寸
    
    ### 操作步骤
    1. 在左侧上传数据文件（CSV或Excel）
    2. 选择图表类型（折线图/散点图）
    3. 选择X轴列
    4. 在Y1轴框中选择要显示在左侧的列
    5. （可选）在Y2轴框中选择要显示在右侧的列
    6. 选择数值小数位数（0-6位）
    7. 配置其他选项（网格、高度等）
    8. 点击"生成图表"按钮
    9. 可以继续添加更多图表
    
    ### 交互操作
    - **缩放区域**: 鼠标拖动选择区域进行放大
    - **滚轮缩放**: 鼠标悬停在Y轴上时滚动滚轮缩放Y轴范围
    - **平移**: 双击后拖动图表
    - **重置**: 双击图表恢复原始视图
    - **联动悬停**: 鼠标悬停时显示纵向虚线，同时显示所有曲线在该位置的值
    - **图例**: 点击图例可以显示/隐藏对应曲线
    
    ### 提示
    - 确保数据文件第一行为列名
    - 数值列会自动识别
    - Y1轴和Y2轴可以各自选择多条曲线
    - Y轴标题默认为该轴选择的第一个特征名
    - 当不同数据范围差异大时，使用Y2轴可获得更好的可视化效果
    - 调整小数位数可以控制显示精度，避免数值过长或过短
    - 💡 散点图使用WebGL加速，即使数万个数据点也能流畅缩放
    """)

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>交互式绘图工具 v1.0 | Powered by Streamlit & Plotly</div>",
    unsafe_allow_html=True
)

