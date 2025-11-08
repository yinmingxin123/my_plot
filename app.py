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
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = {}  # 记录每个图表是否处于编辑模式
if 'confirm_clear' not in st.session_state:
    st.session_state.confirm_clear = False  # 确认清空所有图表的状态

# CSS样式
st.markdown("""
<style>
/* 图表之间的实线分隔 - 和属性虚线一样粗 */
.chart-separator {
    border-top: 2px solid #cccccc;
    margin: 30px 0;
}

/* 属性和图表之间的虚线分隔 - 更疏的间距 */
.property-separator {
    border-top: 2px dashed #cccccc;
    border-image: repeating-linear-gradient(to right, #cccccc 0, #cccccc 10px, transparent 10px, transparent 18px) 1;
    margin: 20px 0;
}

/* 虚线框样式容器 */
.add-chart-container {
    margin: 20px 0;
}

/* 虚线框按钮样式 - 使用最强优先级 */
.add-chart-container div[data-testid="stButton"] button,
.add-chart-container button[kind="primary"],
.add-chart-container button[kind="secondary"],
.add-chart-container button {
    border: 2px dashed #cccccc !important;
    border-radius: 8px !important;
    padding: 40px 20px !important;
    height: auto !important;
    min-height: 120px !important;
    background-color: #fafafa !important;
    background-image: none !important;
    color: #666666 !important;
    font-size: 18px !important;
    font-weight: 400 !important;
    transition: all 0.3s ease !important;
    position: relative !important;
    text-align: center !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}

.add-chart-container div[data-testid="stButton"] button:hover,
.add-chart-container button:hover {
    border-color: #1f77b4 !important;
    background-color: #f0f8ff !important;
    color: #1f77b4 !important;
    transform: none !important;
}

.add-chart-container div[data-testid="stButton"] button:focus,
.add-chart-container button:focus {
    box-shadow: none !important;
    border-color: #1f77b4 !important;
}

/* 在按钮文字前添加加号 */
.add-chart-container div[data-testid="stButton"] button::before,
.add-chart-container button::before {
    content: '+';
    display: block;
    font-size: 50px;
    font-weight: 200;
    line-height: 1;
    margin-bottom: 8px;
    color: inherit;
}

</style>
""", unsafe_allow_html=True)

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
        'title': {
            'text': chart_config['title'],
            'xanchor': 'left',
            'x': 0
        },
        'xaxis': {
            'title': {
                'text': chart_config['x_column']
            },
            'showgrid': chart_config['show_grid'],
            'showline': True,
            'zeroline': True,
            'fixedrange': False,
            'exponentformat': 'none',  # 不使用科学计数法
            'separatethousands': True   # 千位分隔符
        },
        'yaxis': {
            'title': {
                'text': y1_title
            },
            'showgrid': chart_config['show_grid'],
            'showline': True,
            'zeroline': True,
            'fixedrange': False,
            'exponentformat': 'none',  # 不使用科学计数法
            'tickformat': tick_format   # 设置刻度格式
        },
        'hovermode': 'x unified',  # 显示所有曲线的值，带纵向虚线
        'width': chart_config.get('width', 1200),
        'height': chart_config['height'],
        'showlegend': True,
        'legend': {
            'orientation': 'v',
            'yanchor': 'top',
            'y': 1,
            'xanchor': 'left',
            'x': 1.10  # 图例位置：在Y2轴名称右侧，保持适当间距
        },
        'dragmode': 'zoom'  # 支持缩放模式
    }
    
    # 如果有双y轴
    if has_dual_axis:
        y2_title = y2_columns[0] if len(y2_columns) > 0 else 'Y2轴'
        layout_config['yaxis2'] = {
            'title': {
                'text': y2_title
            },
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
    
    # 启用滚轮缩放和标题编辑
    config = {
        'scrollZoom': True,  # 启用滚轮缩放
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToAdd': ['drawopenpath', 'eraseshape'],
        'editable': True,  # 启用标题编辑
        'edits': {
            'titleText': True,  # 可编辑图表标题
            'axisTitleText': True,  # 可编辑坐标轴标题
        }
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

# 添加图表到列表的回调函数
def add_new_chart(position=None):
    """添加新图表，position为None表示添加到末尾，否则插入到指定位置后"""
    new_chart = {
        'title': f"图表 {len(st.session_state.charts) + 1}",
        'chart_type': '折线图',
        'x_column': st.session_state.data.columns[0] if st.session_state.data is not None else '',
        'y1_columns': [],
        'y2_columns': [],
        'show_grid': True,
        'width': 2000,  # 图表宽度
        'height': 500,
        'decimal_places': 2,
        'is_configured': False  # 标记图表是否已配置
    }
    if position is None:
        st.session_state.charts.append(new_chart)
        new_idx = len(st.session_state.charts) - 1
    else:
        st.session_state.charts.insert(position + 1, new_chart)
        new_idx = position + 1
    st.session_state.edit_mode[new_idx] = True  # 新图表默认打开编辑模式

# 渲染单个图表区域
def render_chart_area(idx, chart_config, data, columns):
    """渲染单个图表区域，包括属性面板和图表显示"""
    
    # 使用容器包裹整个图表区域
    with st.container():
        # 标题栏和操作按钮
        col_title, col_edit, col_delete = st.columns([5, 1.5, 1.5])
        with col_title:
            st.subheader(f"{idx + 1}. {chart_config['title']}")
        with col_edit:
            # 切换编辑模式
            edit_label = "收起属性" if st.session_state.edit_mode.get(idx, False) else "编辑属性"
            if st.button(f"⚙️ {edit_label}", key=f"edit_toggle_{idx}"):
                st.session_state.edit_mode[idx] = not st.session_state.edit_mode.get(idx, False)
                st.rerun()
        with col_delete:
            if st.button("🗑️ 删除该图", key=f"delete_{idx}"):
                st.session_state.charts.pop(idx)
                if idx in st.session_state.edit_mode:
                    del st.session_state.edit_mode[idx]
                st.rerun()
        
        # 属性编辑面板（仅在编辑模式下显示）
        if st.session_state.edit_mode.get(idx, False):
            st.markdown("##### 📋 图表属性")
            
            col1, col2 = st.columns(2)
            
            with col1:
                new_title = st.text_input(
                    "图表标题", 
                    value=chart_config['title'],
                    key=f"title_{idx}",
                    help="双击图表可快速修改标题"
                )
                new_chart_type = st.selectbox(
                    "图表类型", 
                    ['折线图', '散点图'],
                    index=['折线图', '散点图'].index(chart_config['chart_type']),
                    key=f"type_{idx}"
                )
                new_x_column = st.selectbox(
                    "X轴 (横坐标)", 
                    columns,
                    index=columns.index(chart_config['x_column']) if chart_config['x_column'] in columns else 0,
                    key=f"x_{idx}"
                )
                new_y1_columns = st.multiselect(
                    "Y1轴 (左侧纵坐标)", 
                    columns,
                    default=chart_config['y1_columns'],
                    help="可以选择多个列显示在左侧Y轴",
                    key=f"y1_{idx}"
                )
            
            with col2:
                new_width = st.slider(
                    "图表宽度 (像素)", 
                    600, 2000, 
                    chart_config.get('width', 1200), 
                    50,
                    key=f"width_{idx}"
                )
                new_height = st.slider(
                    "图表高度 (像素)", 
                    300, 800, 
                    chart_config['height'], 
                    50,
                    key=f"height_{idx}"
                )
                new_show_grid = st.checkbox(
                    "显示网格", 
                    value=chart_config['show_grid'],
                    key=f"grid_{idx}"
                )
                new_decimal_places = st.selectbox(
                    "数值小数位数",
                    options=[0, 1, 2, 3, 4, 5, 6],
                    index=chart_config['decimal_places'],
                    help="控制悬浮框和坐标轴刻度显示的小数位数",
                    key=f"decimal_{idx}"
                )
                new_y2_columns = st.multiselect(
                    "Y2轴 (右侧纵坐标)", 
                    columns,
                    default=chart_config['y2_columns'],
                    help="可选，选择后将在右侧显示独立的Y轴",
                    key=f"y2_{idx}"
                )
            
            # 应用按钮
            if st.button("✅ 应用修改", key=f"apply_{idx}", type="primary"):
                if not new_y1_columns and not new_y2_columns:
                    st.error("请至少为Y1轴或Y2轴选择一个列！")
                else:
                    # 更新图表配置
                    st.session_state.charts[idx].update({
                        'title': new_title,
                        'chart_type': new_chart_type,
                        'x_column': new_x_column,
                        'y1_columns': new_y1_columns,
                        'y2_columns': new_y2_columns,
                        'show_grid': new_show_grid,
                        'width': new_width,
                        'height': new_height,
                        'decimal_places': new_decimal_places,
                        'is_configured': True
                    })
                    st.success("✅ 配置已更新！")
                    st.rerun()
            
            # 属性和图表之间的虚线分隔
            st.markdown('<div class="property-separator"></div>', unsafe_allow_html=True)
        
        # 图表显示区域
        if chart_config['is_configured'] and (chart_config['y1_columns'] or chart_config['y2_columns']):
            try:
                fig, config = create_plotly_chart(chart_config, data)
                st.plotly_chart(fig, use_container_width=False, config=config, key=f"chart_{idx}")
            except Exception as e:
                st.error(f"绘制图表出错: {str(e)}")
        else:
            # 未配置时显示提示
            st.info("👆 请在上方编辑属性并点击「应用修改」来绘制图表")

# 主界面
if st.session_state.data is not None:
    data = st.session_state.data
    columns = data.columns.tolist()
    
    st.header("📊 图表管理")
    
    # 如果没有图表，显示创建虚线框
    if not st.session_state.charts:
        st.markdown('<div class="add-chart-container">', unsafe_allow_html=True)
        if st.button("新增绘图", key="add_first", use_container_width=True):
            add_new_chart()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # 显示所有图表
        for idx, chart_config in enumerate(st.session_state.charts):
            render_chart_area(idx, chart_config, data, columns)
            
            # 图表之间的实线分隔
            st.markdown('<div class="chart-separator"></div>', unsafe_allow_html=True)
            
            # 虚线框添加按钮
            st.markdown('<div class="add-chart-container">', unsafe_allow_html=True)
            if st.button("新增绘图", key=f"add_after_{idx}", use_container_width=True):
                add_new_chart(position=idx)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    # 底部操作
    if st.session_state.charts:
        st.markdown("---")
        st.markdown("#### 批量操作")
        
        # 使用两列布局，左侧放清空按钮，右侧放确认按钮
        if not st.session_state.confirm_clear:
            if st.button("🗑️ 清空所有图表", key="clear_all_btn", type="secondary"):
                st.session_state.confirm_clear = True
                st.rerun()
        else:
            st.warning(f"⚠️ 确定要清空所有 {len(st.session_state.charts)} 个图表吗？此操作无法撤销！")
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("✅ 确认清空", key="confirm_clear_btn", type="primary"):
                    st.session_state.charts = []
                    st.session_state.edit_mode = {}
                    st.session_state.confirm_clear = False
                    st.rerun()
            with col2:
                if st.button("❌ 取消", key="cancel_clear_btn"):
                    st.session_state.confirm_clear = False
                    st.rerun()
        
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
    - ✅ 多图表管理，每个图表独立配置
    - ✅ 在同一图区重新绘制，不创建新图区
    - ✅ 自适应尺寸
    
    ### 操作步骤
    1. **上传数据**: 在左侧上传数据文件（CSV或Excel）
    2. **创建图表**: 点击虚线框"新增绘图"按钮
    3. **编辑属性**: 
       - 在属性面板中设置图表标题、类型
       - 选择X轴列
       - 在Y1轴和Y2轴框中选择要显示的列
       - 选择数值小数位数（0-6位）
       - 配置其他选项（网格、高度等）
    4. **应用配置**: 点击「✅ 应用修改」按钮，图表将在当前区域绘制
    5. **继续添加**: 点击图表下方的虚线框"新增绘图"创建更多图表
    6. **修改图表**: 随时点击「⚙️ 编辑属性」重新调整，应用后在同一区域更新
    
    ### 图表管理
    - **编辑模式**: 点击「⚙️ 编辑属性」打开面板，点击「⚙️ 收起属性」隐藏面板
    - **删除图表**: 点击「🗑️ 删除该图」删除单个图表
    - **清空所有**: 点击底部「🗑️ 清空所有图表」删除所有图表（需确认）
    - **灵活布局**: 可以在任意图表下方添加新图表
    
    ### 交互操作
    - **缩放区域**: 鼠标拖动选择区域进行放大
    - **滚轮缩放**: 鼠标悬停在Y轴上时滚动滚轮缩放Y轴范围
    - **平移**: 双击后拖动图表
    - **重置**: 双击图表恢复原始视图
    - **联动悬停**: 鼠标悬停时显示纵向虚线，同时显示所有曲线在该位置的值
    - **图例**: 点击图例可以显示/隐藏对应曲线
    - **编辑标题**: 双击图表标题或坐标轴标题可以直接编辑（点击图表外保存）
    
    ### 提示
    - 确保数据文件第一行为列名
    - 数值列会自动识别
    - Y1轴和Y2轴可以各自选择多条曲线
    - Y轴标题默认为该轴选择的第一个特征名
    - 当不同数据范围差异大时，使用Y2轴可获得更好的可视化效果
    - 调整小数位数可以控制显示精度，避免数值过长或过短
    - 💡 散点图使用WebGL加速，即使数万个数据点也能流畅缩放
    - 💡 修改属性后点击「应用修改」，图表会在原位置重新绘制，不会创建新图区
    - 💡 双击图表标题、X轴标题或Y轴标题可以快速修改文字
    """)

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>交互式绘图工具 v1.0 | Developer: yinmingxin</div>",
    unsafe_allow_html=True
)

