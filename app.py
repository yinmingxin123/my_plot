import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import ast
import numpy as np

st.set_page_config(page_title="绘图小工具-by YMX", layout="wide")

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
if 'list_columns_info' not in st.session_state:
    st.session_state.list_columns_info = {}  # 记录列表列信息
if 'expanded_list_columns' not in st.session_state:
    st.session_state.expanded_list_columns = {}  # 缓存已展开的列表列数据
if 'parsed_list_columns' not in st.session_state:
    st.session_state.parsed_list_columns = {} # 缓存已解析的列表列

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

def parse_list_string(s):
    """尝试将字符串解析为列表"""
    if pd.isna(s) or s is None:
        return None
    if isinstance(s, str):
        s = s.strip()
        if s.startswith('[') and s.endswith(']'):
            try:
                return ast.literal_eval(s)
            except:
                return None
    return None

def detect_list_columns(df):
    """快速检测哪些列是列表列（不进行实际展开）"""
    list_columns_info = {}
    
    for col in df.columns:
        # 只检查前几行以快速判断
        sample_values = df[col].dropna().head(5)
        if len(sample_values) == 0:
            continue
            
        # 尝试解析第一个非空值
        first_val = sample_values.iloc[0]
        parsed = parse_list_string(first_val)
        
        if parsed is not None and isinstance(parsed, list):
            # 快速扫描确定最大长度
            max_length = len(parsed)
            # 仅检查前5个非空值来估计最大长度，避免完整扫描
            for val in df[col].dropna().head(5).iloc[1:]:
                parsed_val = parse_list_string(val)
                if parsed_val and isinstance(parsed_val, list):
                    max_length = max(max_length, len(parsed_val))
            
            # 只记录是列表列，不展开
            list_columns_info[col] = {
                'num_channels': max_length,
                'is_list_column': True
            }
    
    return list_columns_info

def expand_list_column_lazy(df, col_name, channel_indices=None):
    """
    按需展开列表列（高效缓存版本）
    第一次展开时解析整列并缓存为Numpy数组，后续直接从缓存中提取。
    """
    if col_name not in df.columns:
        return pd.DataFrame()

    # 检查是否已解析并缓存为numpy数组
    if col_name in st.session_state.parsed_list_columns:
        parsed_data_np = st.session_state.parsed_list_columns[col_name]
        max_length = parsed_data_np.shape[1]
    else:
        # --- 昂贵的解析步骤，仅在首次需要时执行 ---
        with st.spinner(f"⏳ 正在首次解析列表列 '{col_name}'... 这可能需要一些时间，请稍候。"):
            
            # 1. 向量化解析字符串
            # 使用 apply 比 for 循环略快，并能更好地处理 Series
            def parse_row(val):
                if isinstance(val, str):
                    val = val.strip()
                    if val.startswith('[') and val.endswith(']'):
                        try:
                            # 使用更快的ujson（如果安装了），否则回退到ast
                            return ast.literal_eval(val)
                        except (ValueError, SyntaxError):
                            return None
                return None

            # parsed_values is now a Series of lists or None
            parsed_values = df[col_name].apply(parse_row)

            # 2. 转换为高效的 NumPy 数组
            # 计算最大长度
            max_length = parsed_values.dropna().apply(len).max()
            if pd.isna(max_length):
                max_length = 0
            
            num_rows = len(df)
            parsed_data_np = np.full((num_rows, int(max_length)), np.nan, dtype=float)

            # 过滤掉None值以加速填充
            valid_rows = parsed_values.dropna()

            # 填充 NumPy 数组
            for i, row_list in valid_rows.items():
                if isinstance(row_list, list):
                    len_row = len(row_list)
                    try:
                        # 尝试直接转换，如果失败则逐个元素转换
                        parsed_data_np[i, :len_row] = row_list
                    except ValueError: # Happens if list contains non-numeric strings
                        for j, item in enumerate(row_list):
                            if j < max_length:
                                try:
                                    parsed_data_np[i, j] = float(item)
                                except (ValueError, TypeError):
                                    pass # Keep as NaN

            # 存入 session state 缓存
            st.session_state.parsed_list_columns[col_name] = parsed_data_np
        st.success(f"✅ 列表列 '{col_name}' 解析完成并已缓存！")

    # --- 从缓存中快速提取数据 ---
    if channel_indices is None:
        channel_indices = list(range(max_length))

    result_dict = {}
    for i in channel_indices:
        if i < max_length:
            channel_name = f"{col_name} #{i+1}"
            result_dict[channel_name] = parsed_data_np[:, i]

    return pd.DataFrame(result_dict)

def load_data(uploaded_file):
    """加载CSV或Excel文件（不立即展开列表列）"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("不支持的文件格式，请上传CSV或Excel文件")
            return None, None
        
        # 只检测列表列，不展开
        list_columns_info = detect_list_columns(df)
        
        return df, list_columns_info
    except Exception as e:
        st.error(f"读取文件出错: {str(e)}")
        return None, None

def render_column_selector_v2(label, all_columns, default_selected, key_prefix, list_columns_info, original_df):
    """
    渲染优化的列选择器（虚拟滚动、二级菜单、按需展开）
    
    Args:
        label: 选择器标签
        all_columns: 所有原始列名
        default_selected: 默认已选中的列（可能包含通道名）
        key_prefix: key前缀
        list_columns_info: 列表列信息字典
        original_df: 原始DataFrame（用于按需展开）
    
    Returns:
        dict: {'normal': [...], 'list_columns': {'col': [channel_indices, ...]}}
    """
    st.write(label)
    
    # 分离普通列和列表列
    normal_columns = [col for col in all_columns if col not in list_columns_info]
    list_columns = [col for col in all_columns if col in list_columns_info]
    
    # 初始化选择状态的session state key
    selection_key = f"{key_prefix}_selections"
    if selection_key not in st.session_state:
        st.session_state[selection_key] = {
            'normal': [],
            'list_columns': {}
        }
    
    # 初始化展开状态的session state key
    expand_key = f"{key_prefix}_expanded"
    if expand_key not in st.session_state:
        st.session_state[expand_key] = {}
    
    # 批量操作版本号：每次批量操作时递增，强制重新创建所有复选框
    version_key = f"{key_prefix}_version"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0
    
    # 虚拟滚动：初始化加载数量
    load_count_key = f"{key_prefix}_load_count"
    if load_count_key not in st.session_state:
        st.session_state[load_count_key] = 20  # 初始加载20列
    
    # 创建一个带滚动的容器
    with st.expander("🔽 选择列", expanded=False):
        # 确保滚动容器有正确的样式
        st.markdown("""
        <style>
        .stExpander > div > div {
            max-height: 500px !important;
            overflow-y: auto !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 渲染普通列（虚拟滚动）
        if normal_columns:
            st.markdown("**📄 普通列**")
            
            # 只显示前N列
            visible_normal_count = min(st.session_state[load_count_key], len(normal_columns))
            
            for idx, col in enumerate(normal_columns[:visible_normal_count]):
                # 检查是否在选择列表中
                is_selected = col in st.session_state[selection_key]['normal']
                
                checkbox_state = st.checkbox(
                    col,
                    value=is_selected,
                    key=f"{key_prefix}_normal_{col}"
                )
                
                # 更新session state
                if checkbox_state:
                    if col not in st.session_state[selection_key]['normal']:
                        st.session_state[selection_key]['normal'].append(col)
                else:
                    if col in st.session_state[selection_key]['normal']:
                        st.session_state[selection_key]['normal'].remove(col)
            
            # 显示"加载更多"按钮
            if visible_normal_count < len(normal_columns):
                remaining = len(normal_columns) - visible_normal_count
                if st.button(f"⬇️ 加载更多 ({remaining} 列未显示)", key=f"{key_prefix}_load_more_normal"):
                    st.session_state[load_count_key] += 20
                    st.rerun()
            
            if list_columns:
                st.markdown("---")
        
        # 渲染列表列（使用按钮控制展开/收起）
        if list_columns:
            st.markdown("**📊 列表列（点击展开通道选择）**")
            
            for list_col in list_columns:
                num_channels = list_columns_info[list_col]['num_channels']
                
                # 初始化该列表列的选择状态
                if list_col not in st.session_state[selection_key]['list_columns']:
                    st.session_state[selection_key]['list_columns'][list_col] = []
                
                # 初始化展开状态
                if list_col not in st.session_state[expand_key]:
                    st.session_state[expand_key][list_col] = False
                
                # 统计已选中的通道数
                selected_count = len(st.session_state[selection_key]['list_columns'].get(list_col, []))
                
                # 显示列表列标题和操作按钮
                col_header, col_btn1, col_btn2, col_btn3 = st.columns([3, 1, 1, 1])
                
                with col_header:
                    expand_icon = "🔽" if st.session_state[expand_key].get(list_col, False) else "▶️"
                    if st.button(
                        f"{expand_icon} **{list_col}** ({selected_count}/{num_channels} 已选)",
                        key=f"{key_prefix}_{list_col}_toggle",
                        use_container_width=True
                    ):
                        st.session_state[expand_key][list_col] = not st.session_state[expand_key].get(list_col, False)
                        st.rerun()
                
                with col_btn1:
                    if st.button("✅", key=f"{key_prefix}_{list_col}_select_all", use_container_width=True, help="全选"):
                        # 执行全选并递增版本号，强制重新创建所有复选框
                        st.session_state[selection_key]['list_columns'][list_col] = list(range(num_channels))
                        st.session_state[version_key] += 1
                        st.rerun()
                
                with col_btn2:
                    if st.button("🔄", key=f"{key_prefix}_{list_col}_invert", use_container_width=True, help="反选"):
                        # 执行反选并递增版本号，强制重新创建所有复选框
                        current = set(st.session_state[selection_key]['list_columns'].get(list_col, []))
                        all_indices = set(range(num_channels))
                        st.session_state[selection_key]['list_columns'][list_col] = sorted(list(all_indices - current))
                        st.session_state[version_key] += 1
                        st.rerun()
                
                with col_btn3:
                    if st.button("❌", key=f"{key_prefix}_{list_col}_clear", use_container_width=True, help="清空"):
                        # 执行清空并递增版本号，强制重新创建所有复选框
                        st.session_state[selection_key]['list_columns'][list_col] = []
                        st.session_state[version_key] += 1
                        st.rerun()
                
                # 如果展开，显示通道选择（虚拟滚动）
                if st.session_state[expand_key].get(list_col, False):
                    st.markdown('<div style="margin-left: 20px; padding: 10px; border-left: 2px solid #ccc; background-color: #f8f9fa;">', unsafe_allow_html=True)
                    
                    # 虚拟滚动：通道加载计数
                    channel_load_key = f"{key_prefix}_{list_col}_channel_load"
                    if channel_load_key not in st.session_state:
                        st.session_state[channel_load_key] = 20
                    
                    visible_channels = min(st.session_state[channel_load_key], num_channels)
                    
                    # 渲染通道选择（使用网格布局节省空间）
                    cols_per_row = 4
                    for i in range(0, visible_channels, cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j in range(cols_per_row):
                            channel_idx = i + j
                            if channel_idx < visible_channels:
                                with cols[j]:
                                    # 检查是否在已选中列表中
                                    is_selected = channel_idx in st.session_state[selection_key]['list_columns'].get(list_col, [])
                                    
                                    # 在key中加入版本号，每次批量操作后会强制重新创建widget
                                    checkbox_state = st.checkbox(
                                        f"#{channel_idx+1}",
                                        value=is_selected,
                                        key=f"{key_prefix}_{list_col}_ch{channel_idx}_v{st.session_state[version_key]}"
                                    )
                                    
                                    # 更新选择状态
                                    current_selection = st.session_state[selection_key]['list_columns'][list_col]
                                    if checkbox_state:
                                        if channel_idx not in current_selection:
                                            # 使用重新赋值新列表的方式，而不是原地修改
                                            new_selection = sorted(current_selection + [channel_idx])
                                            st.session_state[selection_key]['list_columns'][list_col] = new_selection
                                    else:
                                        if channel_idx in current_selection:
                                            # 使用列表推导式创建新列表
                                            new_selection = [c for c in current_selection if c != channel_idx]
                                            st.session_state[selection_key]['list_columns'][list_col] = new_selection
                    
                    # 显示"加载更多通道"按钮
                    if visible_channels < num_channels:
                        remaining_channels = num_channels - visible_channels
                        if st.button(
                            f"⬇️ 加载更多通道 ({remaining_channels} 个未显示)", 
                            key=f"{key_prefix}_{list_col}_load_more_channels"
                        ):
                            st.session_state[channel_load_key] += 20
                            st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("---")
    
    # 统计并显示已选中的列
    total_normal = len(st.session_state[selection_key]['normal'])
    total_channels = sum(len(channels) for channels in st.session_state[selection_key]['list_columns'].values())
    total_selected = total_normal + total_channels
    
    if total_selected > 0:
        summary_parts = []
        if total_normal > 0:
            summary_parts.append(f"{total_normal} 个普通列")
        if total_channels > 0:
            summary_parts.append(f"{total_channels} 个通道")
        st.success(f"✅ 已选中: {', '.join(summary_parts)}")
    else:
        st.warning("⚠️ 未选中任何列")
    
    return st.session_state[selection_key]

def prepare_plot_data(original_df, selections, list_columns_info):
    """
    准备绘图数据（按需展开列表列）
    
    Args:
        original_df: 原始DataFrame
        selections: 选择字典 {'normal': [...], 'list_columns': {'col': [indices]}}
        list_columns_info: 列表列信息
    
    Returns:
        合并后的DataFrame，包含所有需要的列
    """
    result_df = original_df.copy()
    
    # 按需展开选中的列表列通道
    for list_col, channel_indices in selections.get('list_columns', {}).items():
        if not channel_indices:
            continue
            
        # 检查缓存
        cache_key = f"{list_col}_{'_'.join(map(str, sorted(channel_indices)))}"
        if cache_key not in st.session_state.expanded_list_columns:
            # 展开列表列
            expanded_df = expand_list_column_lazy(original_df, list_col, channel_indices)
            st.session_state.expanded_list_columns[cache_key] = expanded_df
        else:
            expanded_df = st.session_state.expanded_list_columns[cache_key]
        
        # 合并到结果DataFrame
        for col in expanded_df.columns:
            result_df[col] = expanded_df[col]
    
    return result_df

def create_plotly_chart(chart_config, data):
    """根据配置创建Plotly图表"""
    
    # 判断是否有双y轴
    y1_columns = chart_config.get('y1_columns', [])
    y2_columns = chart_config.get('y2_columns', [])
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
            st.session_state.data, st.session_state.list_columns_info = load_data(uploaded_file)
            st.session_state.filename = uploaded_file.name
            # --- 重置所有与旧数据相关的状态 ---
            st.session_state.charts = []
            st.session_state.edit_mode = {}
            st.session_state.expanded_list_columns = {}
            st.session_state.parsed_list_columns = {}
            st.session_state.confirm_clear = False
            
            # 清理所有与图表列选择相关的动态状态 (例如 y1_0_selections, y2_0_expanded 等)
            # 这些状态的key通常以 'y1_' 或 'y2_' 开头
            keys_to_delete = [key for key in st.session_state.keys() if key.startswith(('y1_', 'y2_'))]
            for key in keys_to_delete:
                del st.session_state[key]
        
        if st.session_state.data is not None:
            st.success(f"✅ 已加载: {uploaded_file.name}")
            st.info(f"数据形状: {st.session_state.data.shape[0]} 行 × {st.session_state.data.shape[1]} 列")
            
            # 显示列表列信息
            if st.session_state.list_columns_info:
                with st.expander("📊 检测到列表列"):
                    for col_name, info in st.session_state.list_columns_info.items():
                        st.write(f"**{col_name}** → {info['num_channels']} 个通道")
                        st.write(f"  选择后将展开为: {col_name} #1 ~ #{info['num_channels']}")
            
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
                # 使用新的列选择器V2
                y1_default = chart_config.get('y1_selected_columns', [])
                y1_selections = render_column_selector_v2(
                    "Y1轴 (左侧纵坐标)",
                    columns,
                    y1_default,
                    f"y1_{idx}",
                    st.session_state.list_columns_info,
                    data
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
                # 使用新的列选择器V2
                y2_default = chart_config.get('y2_selected_columns', [])
                y2_selections = render_column_selector_v2(
                    "Y2轴 (右侧纵坐标)",
                    columns,
                    y2_default,
                    f"y2_{idx}",
                    st.session_state.list_columns_info,
                    data
                )
            
            # 应用按钮
            if st.button("✅ 应用修改", key=f"apply_{idx}", type="primary"):
                # 检查是否有选中列
                y1_total = len(y1_selections['normal']) + sum(len(chs) for chs in y1_selections['list_columns'].values())
                y2_total = len(y2_selections['normal']) + sum(len(chs) for chs in y2_selections['list_columns'].values())
                
                if y1_total == 0 and y2_total == 0:
                    st.error("请至少为Y1轴或Y2轴选择一个列！")
                else:
                    # 生成实际的列名列表（用于绘图）
                    y1_column_names = y1_selections['normal'].copy()
                    for list_col, channel_indices in y1_selections['list_columns'].items():
                        for ch_idx in channel_indices:
                            y1_column_names.append(f"{list_col} #{ch_idx+1}")
                    
                    y2_column_names = y2_selections['normal'].copy()
                    for list_col, channel_indices in y2_selections['list_columns'].items():
                        for ch_idx in channel_indices:
                            y2_column_names.append(f"{list_col} #{ch_idx+1}")
                    
                    # 更新图表配置
                    st.session_state.charts[idx].update({
                        'title': new_title,
                        'chart_type': new_chart_type,
                        'x_column': new_x_column,
                        'y1_columns': y1_column_names,  # 实际列名
                        'y2_columns': y2_column_names,  # 实际列名
                        'y1_selections': y1_selections,  # 保存选择状态
                        'y2_selections': y2_selections,  # 保存选择状态
                        'y1_selected_columns': y1_column_names,  # 用于下次打开时回显
                        'y2_selected_columns': y2_column_names,
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
        if chart_config['is_configured'] and (chart_config.get('y1_columns') or chart_config.get('y2_columns')):
            try:
                # 准备绘图数据（按需展开列表列）
                y1_selections = chart_config.get('y1_selections', {'normal': chart_config.get('y1_columns', []), 'list_columns': {}})
                y2_selections = chart_config.get('y2_selections', {'normal': chart_config.get('y2_columns', []), 'list_columns': {}})
                
                # 合并Y1和Y2的选择，一次性展开所有需要的列表列
                all_selections = {
                    'normal': list(set(y1_selections.get('normal', []) + y2_selections.get('normal', []))),
                    'list_columns': {}
                }
                for list_col in set(list(y1_selections.get('list_columns', {}).keys()) + list(y2_selections.get('list_columns', {}).keys())):
                    ch1 = y1_selections.get('list_columns', {}).get(list_col, [])
                    ch2 = y2_selections.get('list_columns', {}).get(list_col, [])
                    all_selections['list_columns'][list_col] = list(set(ch1 + ch2))
                
                # 准备完整的数据
                plot_data = prepare_plot_data(data, all_selections, st.session_state.list_columns_info)
                
                # 创建图表
                fig, config = create_plotly_chart(chart_config, plot_data)
                st.caption("💡 提示：可框选区域进行放大；鼠标悬停在坐标轴上可拖动，滚动滚轮可进行缩放；双击可重置视图。")
                st.plotly_chart(fig, use_container_width=False, config=config, key=f"chart_{idx}")
            except Exception as e:
                st.error(f"绘制图表出错: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
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
    - ✅ **自动解析列表列**：支持字符串形式的列表数据（如 "[2, 5, 8]"），自动展开为多个通道
    - ✅ **智能通道管理**：列表列自动分组显示，可选择性绘制指定通道
    - ✅ 交互式折线图和散点图
    - ✅ 自由选择X轴和多个Y轴列
    - ✅ **下拉勾选式列选择**：改进的列选择器，选中后保持可见
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
    
    ### 列表列功能
    - **自动检测**：系统会自动检测包含列表字符串的列（如 `"[2, 5, 8]"`）
    - **自动展开**：列表列会被展开为多个通道列，格式为 `列名 #通道号`
    - **示例**：如果列 `feature` 包含 `"[2, 5, 8]"`，会展开为：
      - `feature #1` → 值为 2, 3, 4, ...
      - `feature #2` → 值为 5, 7, 6, ...
      - `feature #3` → 值为 8, 9, 16, ...
    - **分组显示**：在列选择器中，列表列的通道会分组显示，便于选择
    - **共享X轴**：所有通道共享相同的X轴（通常是时间序列）
    - **灵活绘制**：可以选择性地只显示需要的通道
    
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
    - 💡 列表列支持不同长度，系统会自动处理缺失值
    """)

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>交互式绘图工具 v1.0 | Developer: yinmingxin</div>",
    unsafe_allow_html=True
)

