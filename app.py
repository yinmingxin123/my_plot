import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import ast
import numpy as np

st.set_page_config(page_title="绘图小工具-by YMX", layout="wide")

# 大文件阈值配置
LARGE_FILE_THRESHOLD = 500000  # 超过50万行视为大文件
DOWNSAMPLE_TARGET_POINTS = 10000  # 降采样目标点数

# 初始化session state
if 'charts' not in st.session_state:
    st.session_state.charts = []
if 'files_data' not in st.session_state:
    st.session_state.files_data = {}  # {filename: {'data': DataFrame, 'list_columns_info': dict, 'is_large': bool, 'downsampled': DataFrame}}
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = {}  # 记录每个图表是否处于编辑模式
if 'confirm_clear' not in st.session_state:
    st.session_state.confirm_clear = False  # 确认清空所有图表的状态
if 'expanded_list_columns' not in st.session_state:
    st.session_state.expanded_list_columns = {}  # 缓存已展开的列表列数据
if 'parsed_list_columns' not in st.session_state:
    st.session_state.parsed_list_columns = {} # 缓存已解析的列表列
if 'chart_range_mode' not in st.session_state:
    st.session_state.chart_range_mode = {}  # 记录每个图表的显示模式：'downsampled' 或 'original'
if 'chart_range_selection' not in st.session_state:
    st.session_state.chart_range_selection = {}  # 记录每个图表的范围选择（输入框当前值）
if 'confirmed_chart_range' not in st.session_state:
    st.session_state.confirmed_chart_range = {}  # 记录已确认绘制的范围（点击绘制按钮后才更新）
if 'chart_data_ready' not in st.session_state:
    st.session_state.chart_data_ready = {}  # 记录原始数据模式下是否已确认绘制
if 'downsample_ratio' not in st.session_state:
    st.session_state.downsample_ratio = 100  # 默认降采样倍数
if 'histogram_bins' not in st.session_state:
    st.session_state.histogram_bins = {}  # 记录每个直方图的bin数量

# Fragment 函数：原始数据模式的范围选择输入控件
# 使用 @st.fragment 使输入变化时只刷新输入部分，不影响图表
@st.fragment
def render_range_input_controls(idx: int, total_rows: int, downsampled_rows: int, x_col: str, original_data):
    """渲染范围选择输入控件（三向联动）- 作为 fragment，修改时不触发整个页面刷新"""
    """渲染范围选择输入控件（三向联动）"""
    
    # 初始化session_state中的联动值（如果不存在）
    if f'ds_start_{idx}' not in st.session_state:
        # 获取当前范围（原始数据行号）
        current_range = st.session_state.chart_range_selection.get(idx)
        if current_range:
            is_numeric_x = pd.api.types.is_numeric_dtype(original_data[x_col])
            if is_numeric_x:
                # 数值型X轴，current_range是X轴值，需要转换为行号
                x_min = float(original_data[x_col].min())
                x_max = float(original_data[x_col].max())
                x_range = x_max - x_min
                if x_range > 0:
                    default_start_pct = ((float(current_range[0]) - x_min) / x_range * 100)
                    default_end_pct = ((float(current_range[1]) - x_min) / x_range * 100)
                    default_start_row = int(default_start_pct / 100 * total_rows)
                    default_end_row = int(default_end_pct / 100 * total_rows)
                else:
                    default_start_pct = 40.0
                    default_end_pct = 60.0
                    default_start_row = int(total_rows * 0.4)
                    default_end_row = int(total_rows * 0.6)
            else:
                # 非数值型X轴，current_range就是行号
                default_start_row = int(current_range[0])
                default_end_row = int(current_range[1])
                default_start_pct = (default_start_row / total_rows * 100) if total_rows > 0 else 40.0
                default_end_pct = (default_end_row / total_rows * 100) if total_rows > 0 else 60.0
        else:
            # 没有当前范围，使用中间20%
            default_start_pct = 40.0
            default_end_pct = 60.0
            default_start_row = int(total_rows * 0.4)
            default_end_row = int(total_rows * 0.6)
        
        # 计算对应的降采样图行号
        default_start_ds_row = int(default_start_pct / 100 * downsampled_rows)
        default_end_ds_row = int(default_end_pct / 100 * downsampled_rows)
        
        # 初始化session_state
        st.session_state[f'ds_start_{idx}'] = default_start_ds_row
        st.session_state[f'ds_end_{idx}'] = default_end_ds_row
        st.session_state[f'pct_start_{idx}'] = default_start_pct
        st.session_state[f'pct_end_{idx}'] = default_end_pct
        st.session_state[f'row_start_{idx}'] = default_start_row
        st.session_state[f'row_end_{idx}'] = default_end_row
    
    # 定义联动回调函数
    def update_from_ds_start():
        ds_val = st.session_state[f'ds_start_{idx}']
        pct_val = (ds_val / downsampled_rows * 100) if downsampled_rows > 0 else 0
        row_val = int(pct_val / 100 * total_rows)
        st.session_state[f'pct_start_{idx}'] = pct_val
        st.session_state[f'row_start_{idx}'] = row_val
    
    def update_from_ds_end():
        ds_val = st.session_state[f'ds_end_{idx}']
        pct_val = (ds_val / downsampled_rows * 100) if downsampled_rows > 0 else 0
        row_val = int(pct_val / 100 * total_rows)
        st.session_state[f'pct_end_{idx}'] = pct_val
        st.session_state[f'row_end_{idx}'] = row_val
    
    def update_from_pct_start():
        pct_val = st.session_state[f'pct_start_{idx}']
        ds_val = int(pct_val / 100 * downsampled_rows)
        row_val = int(pct_val / 100 * total_rows)
        st.session_state[f'ds_start_{idx}'] = ds_val
        st.session_state[f'row_start_{idx}'] = row_val
    
    def update_from_pct_end():
        pct_val = st.session_state[f'pct_end_{idx}']
        ds_val = int(pct_val / 100 * downsampled_rows)
        row_val = int(pct_val / 100 * total_rows)
        st.session_state[f'ds_end_{idx}'] = ds_val
        st.session_state[f'row_end_{idx}'] = row_val
    
    def update_from_row_start():
        row_val = st.session_state[f'row_start_{idx}']
        pct_val = (row_val / total_rows * 100) if total_rows > 0 else 0
        ds_val = int(pct_val / 100 * downsampled_rows)
        st.session_state[f'pct_start_{idx}'] = pct_val
        st.session_state[f'ds_start_{idx}'] = ds_val
    
    def update_from_row_end():
        row_val = st.session_state[f'row_end_{idx}']
        pct_val = (row_val / total_rows * 100) if total_rows > 0 else 0
        ds_val = int(pct_val / 100 * downsampled_rows)
        st.session_state[f'pct_end_{idx}'] = pct_val
        st.session_state[f'ds_end_{idx}'] = ds_val
    
    # 1️⃣ 降采样图行号输入（带自动联动）
    st.markdown("**1️⃣ 降采样图行号（从hover中读取）**")
    ds_col1, ds_col2 = st.columns(2)
    with ds_col1:
        st.number_input(
            f"起始行号 (降采样图: 0-{downsampled_rows-1})",
            min_value=0,
            max_value=downsampled_rows - 1,
            step=1,
            key=f'ds_start_{idx}',
            on_change=update_from_ds_start,
            help=f"从降采样图hover中看到的行索引（0到{downsampled_rows-1}）"
        )
    with ds_col2:
        st.number_input(
            f"结束行号 (降采样图: 0-{downsampled_rows-1})",
            min_value=0,
            max_value=downsampled_rows - 1,
            step=1,
            key=f'ds_end_{idx}',
            on_change=update_from_ds_end,
            help=f"从降采样图hover中看到的行索引（0到{downsampled_rows-1}）"
        )
    
    # 2️⃣ 百分比输入（带自动联动，精确到4位小数）
    st.markdown("**2️⃣ 百分比**")
    pct_col1, pct_col2 = st.columns(2)
    with pct_col1:
        st.number_input(
            "起始百分比 (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.0001,
            format="%.4f",
            key=f'pct_start_{idx}',
            on_change=update_from_pct_start,
            help="数据起始位置的百分比（0-100%），精确到0.0001%"
        )
    with pct_col2:
        st.number_input(
            "结束百分比 (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.0001,
            format="%.4f",
            key=f'pct_end_{idx}',
            on_change=update_from_pct_end,
            help="数据结束位置的百分比（0-100%），精确到0.0001%"
        )
    
    # 3️⃣ 原始数据行号输入（带自动联动）
    st.markdown("**3️⃣ 原始数据行号**")
    row_col1, row_col2 = st.columns(2)
    with row_col1:
        st.number_input(
            f"起始行号 (原始数据: 0-{total_rows-1})",
            min_value=0,
            max_value=total_rows - 1,
            step=1000,
            key=f'row_start_{idx}',
            on_change=update_from_row_start,
            help=f"原始数据的起始行号（0到{total_rows-1}）"
        )
    with row_col2:
        st.number_input(
            f"结束行号 (原始数据: 0-{total_rows-1})",
            min_value=0,
            max_value=total_rows - 1,
            step=1000,
            key=f'row_end_{idx}',
            on_change=update_from_row_end,
            help=f"原始数据的结束行号（0到{total_rows-1}）"
        )
    
    # 数值验证和显示
    current_ds_start = st.session_state[f'ds_start_{idx}']
    current_ds_end = st.session_state[f'ds_end_{idx}']
    current_pct_start = st.session_state[f'pct_start_{idx}']
    current_pct_end = st.session_state[f'pct_end_{idx}']
    current_row_start = st.session_state[f'row_start_{idx}']
    current_row_end = st.session_state[f'row_end_{idx}']
    
    # 校验：起始必须小于等于结束
    has_error = False
    if current_ds_start > current_ds_end or current_pct_start > current_pct_end or current_row_start > current_row_end:
        st.error("❌ 起始索引不能大于结束索引")
        has_error = True
    
    if not has_error:
        # 更新chart_range_selection
        st.session_state.chart_range_selection[idx] = (current_row_start, current_row_end)
        
        # 计算并显示范围内的数据量
        range_data_count = current_row_end - current_row_start + 1
        range_percentage = (range_data_count / total_rows) * 100
        st.caption(f"📊 选定范围内数据量: {range_data_count:,} 行 ({range_percentage:.2f}%)")
        
        # 数据量警告
        if range_data_count > 1000000:
            st.warning(f"⚠️ 选定范围内数据量较大 ({range_data_count:,} 行)，绘图可能需要较长时间。建议缩小范围。")
        elif range_data_count > 500000:
            st.warning(f"⚠️ 选定范围内数据量较多 ({range_data_count:,} 行)，绘图可能需要数秒时间")

# Fragment 函数：图表属性编辑面板
# 使用 @st.fragment 使属性修改时只刷新属性面板，不影响图表绘制区
@st.fragment
def render_chart_properties_fragment(idx: int, chart_config: dict):
    """渲染图表属性编辑面板 - 作为 fragment，修改属性时不触发整个页面刷新"""
    
    st.markdown("##### 📋 图表属性")
    
    # 获取文件列表
    filenames = list(st.session_state.files_data.keys())
    
    # 如果有多个文件，显示数据源选择
    if len(filenames) > 1:
        st.markdown("**📂 数据来源**")
        current_source = chart_config.get('data_source', None)
        if current_source not in filenames:
            current_source = None
        
        source_index = filenames.index(current_source) if current_source else 0
        new_data_source = st.selectbox(
            "选择数据文件",
            filenames,
            index=source_index,
            key=f"data_source_{idx}",
            help="选择该图表使用的数据文件"
        )
        
        # 如果数据源改变，更新图表配置并重置列选择
        if new_data_source != chart_config.get('data_source'):
            # 更新图表配置
            chart_config['data_source'] = new_data_source
            chart_config['y1_columns'] = []
            chart_config['y2_columns'] = []
            chart_config['y1_selections'] = {'normal': [], 'list_columns': {}}
            chart_config['y2_selections'] = {'normal': [], 'list_columns': {}}
            chart_config['y1_selected_columns'] = []
            chart_config['y2_selected_columns'] = []
            chart_config['is_configured'] = False
            
            # 重置X轴为新数据源的第一列
            if new_data_source and new_data_source in st.session_state.files_data:
                new_data = st.session_state.files_data[new_data_source]['data']
                chart_config['x_column'] = new_data.columns[0] if len(new_data.columns) > 0 else ''
            
            # 清理该图表的所有相关状态
            clear_chart_states(idx)
            
            st.warning(f"⚠️ 数据源已切换到 '{new_data_source}'，列选择已重置")
            st.rerun(scope="app")  # 数据源改变需要刷新整个页面
    
    # 检查是否选择了数据源
    data_source = chart_config.get('data_source')
    if not data_source:
        st.error("⚠️ 请先选择数据来源！")
        return
    
    # 获取对应的数据和列信息
    if data_source not in st.session_state.files_data:
        st.error(f"❌ 数据文件 '{data_source}' 不存在！")
        return
    
    file_info = st.session_state.files_data[data_source]
    data = file_info['data']
    list_columns_info = file_info['list_columns_info']
    is_large_file = file_info.get('is_large', False)
    columns = data.columns.tolist()
    
    # 显示数据行数和文件显示模式
    st.markdown("---")
    st.markdown("### 📊 数据信息与显示模式")
    
    # 显示行数
    row_count = len(data)
    if is_large_file:
        st.info(f"📊 **数据行数: {row_count:,} 行** (大文件)")
    else:
        st.info(f"📊 **数据行数: {row_count:,} 行**")
    
    # 初始化该图表的范围模式（大文件默认降采样，非大文件默认原始数据）
    if idx not in st.session_state.chart_range_mode:
        default_mode = 'downsampled' if is_large_file else 'original'
        st.session_state.chart_range_mode[idx] = default_mode
        st.session_state.chart_data_ready[idx] = True  # 都默认准备好
    
    # 显示模式选择
    mode_col, ratio_col = st.columns([2, 2])
    
    with mode_col:
        current_mode = st.session_state.chart_range_mode[idx]
        estimated_points = max(1000, row_count // st.session_state.downsample_ratio)
        mode_options = {
            'downsampled': f'📉 降采样预览 ({st.session_state.downsample_ratio}x, 约{estimated_points:,}点)',
            'original': '📊 原始数据'
        }
        
        selected_mode = st.radio(
            "文件显示模式",
            options=list(mode_options.keys()),
            format_func=lambda x: mode_options[x],
            index=0 if current_mode == 'downsampled' else 1,
            key=f"display_mode_prop_{idx}",
            horizontal=True,
            help="降采样预览：快速查看概览；原始数据：显示完整颗粒度"
        )
        
        if selected_mode != current_mode:
            st.session_state.chart_range_mode[idx] = selected_mode
            if selected_mode == 'downsampled':
                st.session_state.chart_data_ready[idx] = True
            else:
                st.session_state.chart_data_ready[idx] = False
            st.rerun()
    
    with ratio_col:
        # 降采样倍数设置（仅在降采样模式下显示）
        if selected_mode == 'downsampled':
            new_ratio = st.number_input(
                "降采样倍数",
                min_value=1,
                max_value=1000,
                value=st.session_state.downsample_ratio,
                step=1,
                key=f"downsample_ratio_prop_{idx}",
                help="原始数据行数除以此倍数得到降采样后的点数"
            )
            if new_ratio != st.session_state.downsample_ratio:
                st.session_state.downsample_ratio = new_ratio
                st.rerun()
            
            current_points = max(1000, row_count // st.session_state.downsample_ratio)
            st.caption(f"💡 {row_count:,}行 ÷ {st.session_state.downsample_ratio} = 约{current_points:,}点")
    
    # 首先选择图表类型（放在最前面，因为后续选项依赖于此）
    st.markdown("---")
    st.markdown("### 📈 图表类型")
    chart_types = ['折线图', '散点图', '直方图']
    current_type = chart_config['chart_type']
    if current_type not in chart_types:
        current_type = '折线图'
    new_chart_type = st.selectbox(
        "选择图表类型", 
        chart_types,
        index=chart_types.index(current_type),
        key=f"type_{idx}"
    )
    
    # 重叠模式开关（仅折线图和散点图显示）
    if new_chart_type != '直方图':
        st.markdown("---")
        st.markdown("### 🎨 绘图模式")
        overlay_mode = st.checkbox(
            "🔄 启用重叠模式（多特征共享X轴，每个特征独立Y轴）",
            value=chart_config.get('overlay_mode', False),
            key=f"overlay_mode_{idx}",
            help="启用后，所有选中的特征将绘制在同一图表中，每个特征使用独立的Y轴刻度，并通过颜色关联。适合量纲差异大的多特征对比。"
        )
        
        if overlay_mode:
            st.info("💡 重叠模式已启用：所有Y轴特征将使用独立刻度，通过颜色强关联（曲线、Y轴、图例同色）")
            
            # 重叠模式下的轴排布策略
            axis_placement = st.radio(
                "Y轴排布策略",
                options=['alternate', 'left'],
                format_func=lambda x: '左右交替' if x == 'alternate' else '左侧堆叠',
                index=0 if chart_config.get('axis_placement', 'alternate') == 'alternate' else 1,
                key=f"axis_placement_{idx}",
                horizontal=True,
                help="左右交替：Y轴在左右两侧交替排列；左侧堆叠：所有Y轴在左侧堆叠排列"
            )
        else:
            axis_placement = 'alternate'
    else:
        # 直方图模式下不使用重叠模式
        overlay_mode = False
        axis_placement = 'alternate'
        
        # 直方图特有设置
        st.markdown("---")
        st.markdown("### 📊 直方图设置")
        
        # 初始化bin数量
        if idx not in st.session_state.histogram_bins:
            st.session_state.histogram_bins[idx] = chart_config.get('histogram_bins', 50)
        
        histogram_bins = st.slider(
            "分箱数 (Bins)",
            min_value=5,
            max_value=500,
            value=st.session_state.histogram_bins[idx],
            step=5,
            key=f"hist_bins_{idx}",
            help="控制直方图的分箱数量，数值越大柱子越细"
        )
        st.session_state.histogram_bins[idx] = histogram_bins
        
        # 显示模式选择
        hist_normalize = st.checkbox(
            "归一化显示（概率密度）",
            value=chart_config.get('hist_normalize', False),
            key=f"hist_normalize_{idx}",
            help="勾选后显示概率密度而非频数"
        )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_title = st.text_input(
            "图表标题", 
            value=chart_config['title'],
            key=f"title_{idx}",
            help="双击图表可快速修改标题"
        )
        
        # 非直方图模式才设置直方图默认值
        if new_chart_type != '直方图':
            histogram_bins = chart_config.get('histogram_bins', 50)
            hist_normalize = chart_config.get('hist_normalize', False)
        
        # 直方图模式下不需要选择X轴
        if new_chart_type != '直方图':
            new_x_column = st.selectbox(
                "X轴 (横坐标)", 
                columns,
                index=columns.index(chart_config['x_column']) if chart_config['x_column'] in columns else 0,
                key=f"x_{idx}"
            )
        else:
            # 直方图模式下使用默认的第一列作为X轴（实际不会用到）
            new_x_column = chart_config.get('x_column', columns[0] if columns else '')
        
        # 根据模式显示不同的Y轴选择器
        if new_chart_type == '直方图':
            # 直方图模式：只需要选择要分析的特征
            y1_default = chart_config.get('y1_selected_columns', [])
            y1_selections = render_column_selector_v2(
                "📊 选择要分析的特征（支持多选）",
                columns,
                y1_default,
                f"y1_{idx}",
                list_columns_info,
                data
            )
            # 直方图模式下Y2为空
            y2_selections = {'normal': [], 'list_columns': {}}
        elif overlay_mode:
            # 重叠模式：不区分Y1/Y2，统一选择
            y1_default = chart_config.get('y1_selected_columns', [])
            y1_selections = render_column_selector_v2(
                "Y轴特征（每个特征独立刻度）",
                columns,
                y1_default,
                f"y1_{idx}",
                list_columns_info,
                data
            )
            # 重叠模式下Y2为空
            y2_selections = {'normal': [], 'list_columns': {}}
        else:
            # 普通模式：区分Y1/Y2
            y1_default = chart_config.get('y1_selected_columns', [])
            y1_selections = render_column_selector_v2(
                "Y1轴 (左侧纵坐标)",
                columns,
                y1_default,
                f"y1_{idx}",
                list_columns_info,
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
        
        # 普通模式下显示Y2轴选择器（直方图和重叠模式下不显示）
        if not overlay_mode and new_chart_type != '直方图':
            y2_default = chart_config.get('y2_selected_columns', [])
            y2_selections = render_column_selector_v2(
                "Y2轴 (右侧纵坐标)",
                columns,
                y2_default,
                f"y2_{idx}",
                list_columns_info,
                data
            )
    
    # 应用按钮
    if st.button("✅ 应用修改", key=f"apply_{idx}", type="primary"):
        # 检查是否有选中列
        y1_total = len(y1_selections['normal']) + sum(len(chs) for chs in y1_selections['list_columns'].values())
        y2_total = len(y2_selections['normal']) + sum(len(chs) for chs in y2_selections['list_columns'].values())
        
        if y1_total == 0 and y2_total == 0:
            st.error("请至少选择一个Y轴特征！")
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
            
            # 重叠模式特殊提示
            if overlay_mode:
                total_features = y1_total
                if total_features > 10:
                    st.warning(f"⚠️ 当前选择了 {total_features} 个特征，建议不超过10个以保持图表清晰度。")
            
            # 更新图表配置
            st.session_state.charts[idx].update({
                'title': new_title,
                'chart_type': new_chart_type,
                'data_source': data_source,  # 保存数据源
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
                'overlay_mode': overlay_mode,  # 保存重叠模式
                'axis_placement': axis_placement,  # 保存轴排布策略
                'histogram_bins': histogram_bins,  # 保存直方图分箱数
                'hist_normalize': hist_normalize,  # 保存直方图归一化设置
                'is_configured': True
            })
            st.success("✅ 配置已更新！")
            st.rerun(scope="app")  # 使用 scope="app" 刷新整个页面来更新图表

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

def lttb_downsample(data, x_col, y_cols, threshold):
    """
    使用LTTB算法对数据进行降采样，保留数据特征
    
    Args:
        data: DataFrame，原始数据
        x_col: X轴列名
        y_cols: Y轴列名列表
        threshold: 目标点数
    
    Returns:
        降采样后的DataFrame
    """
    if len(data) <= threshold:
        return data.copy()
    
    # 检查X轴是否为数值类型
    if x_col not in data.columns:
        return simple_downsample(data, threshold)
    
    if not pd.api.types.is_numeric_dtype(data[x_col]):
        # X轴不是数值类型，回退到简单降采样
        return simple_downsample(data, threshold)
    
    # 对每个y列分别进行LTTB降采样，然后合并索引
    all_indices = set()
    
    for y_col in y_cols:
        if y_col not in data.columns:
            continue
        
        # 检查Y轴是否为数值类型
        if not pd.api.types.is_numeric_dtype(data[y_col]):
            continue
        
        # 提取x和y数据，移除NaN
        temp_df = data[[x_col, y_col]].dropna()
        if len(temp_df) <= threshold:
            all_indices.update(temp_df.index)
            continue
        
        # 确保数据是数值类型
        try:
            x_data = temp_df[x_col].astype(float).values
            y_data = temp_df[y_col].astype(float).values
        except (ValueError, TypeError):
            # 无法转换为浮点数，跳过该列
            continue
        
        # LTTB算法
        try:
            sampled_indices = []
            bucket_size = (len(temp_df) - 2) / (threshold - 2)
            
            # 始终包含第一个点
            sampled_indices.append(0)
            
            a = 0  # 上一个选中的点
            for i in range(threshold - 2):
                # 当前桶的范围
                avg_range_start = int(np.floor((i + 1) * bucket_size) + 1)
                avg_range_end = int(np.floor((i + 2) * bucket_size) + 1)
                avg_range_end = min(avg_range_end, len(temp_df))
                
                # 防止空切片
                if avg_range_start >= avg_range_end:
                    continue
                
                # 计算下一个桶的平均点
                avg_x = float(np.mean(x_data[avg_range_start:avg_range_end]))
                avg_y = float(np.mean(y_data[avg_range_start:avg_range_end]))
                
                # 在当前桶中找到形成最大三角形面积的点
                range_offs = int(np.floor((i + 0) * bucket_size) + 1)
                range_to = int(np.floor((i + 1) * bucket_size) + 1)
                
                # 防止越界
                range_offs = min(range_offs, len(temp_df) - 1)
                range_to = min(range_to, len(temp_df))
                
                if range_offs >= range_to:
                    continue
                
                point_a_x = float(x_data[a])
                point_a_y = float(y_data[a])
                
                max_area = -1
                next_a = range_offs
                
                for idx in range(range_offs, range_to):
                    # 计算三角形面积
                    area = abs(
                        (point_a_x - avg_x) * (float(y_data[idx]) - point_a_y) -
                        (point_a_x - float(x_data[idx])) * (avg_y - point_a_y)
                    ) * 0.5
                    
                    if area > max_area:
                        max_area = area
                        next_a = idx
                
                sampled_indices.append(next_a)
                a = next_a
            
            # 始终包含最后一个点
            sampled_indices.append(len(temp_df) - 1)
            
            # 将局部索引转换为原始DataFrame索引
            original_indices = temp_df.iloc[sampled_indices].index
            all_indices.update(original_indices)
        except Exception as e:
            # LTTB算法失败，使用该列的所有索引
            all_indices.update(temp_df.index)
    
    # 合并所有y列的采样点，去重并排序
    if len(all_indices) == 0:
        # 如果LTTB没有采样到任何点，回退到简单降采样
        return simple_downsample(data, threshold)
    
    selected_indices = sorted(list(all_indices))
    
    # 如果采样点太少，补充一些点
    if len(selected_indices) < threshold // 2:
        return simple_downsample(data, threshold)
    
    return data.loc[selected_indices].reset_index(drop=True)

def simple_downsample(data, threshold):
    """
    简单的均匀降采样
    
    Args:
        data: DataFrame，原始数据
        threshold: 目标点数
    
    Returns:
        降采样后的DataFrame
    """
    if len(data) <= threshold:
        return data.copy()
    
    # 均匀采样
    step = len(data) // threshold
    indices = list(range(0, len(data), step))
    
    # 确保包含最后一个点
    if indices[-1] != len(data) - 1:
        indices.append(len(data) - 1)
    
    return data.iloc[indices].reset_index(drop=True)

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

def expand_list_column_lazy(df, col_name, channel_indices=None, data_source=None):
    """
    按需展开列表列（高效缓存版本）
    第一次展开时解析整列并缓存为Numpy数组，后续直接从缓存中提取。
    
    Args:
        df: DataFrame
        col_name: 列名
        channel_indices: 通道索引列表
        data_source: 数据源文件名（用于区分不同文件中的同名列）
    """
    if col_name not in df.columns:
        return pd.DataFrame()

    # 生成缓存键（包含数据源以区分不同文件）
    cache_key = f"{data_source}_{col_name}" if data_source else col_name
    
    # 检查是否已解析并缓存为numpy数组
    if cache_key in st.session_state.parsed_list_columns:
        parsed_data_np = st.session_state.parsed_list_columns[cache_key]
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
            st.session_state.parsed_list_columns[cache_key] = parsed_data_np
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

def clear_chart_states(chart_idx):
    """
    清理指定图表的所有相关session state
    
    Args:
        chart_idx: 图表索引
    """
    # 清理该图表的所有相关状态（列选择、widget状态等）
    keys_to_delete = [key for key in list(st.session_state.keys()) 
                     if key.startswith(f'y1_{chart_idx}_') or 
                        key.startswith(f'y2_{chart_idx}_') or
                        key.startswith(f'x_{chart_idx}') or
                        key.startswith(f'title_{chart_idx}') or
                        key.startswith(f'type_{chart_idx}') or
                        key.startswith(f'grid_{chart_idx}') or
                        key.startswith(f'width_{chart_idx}') or
                        key.startswith(f'height_{chart_idx}') or
                        key.startswith(f'decimal_{chart_idx}') or
                        key.startswith(f'data_source_{chart_idx}')]
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]

def load_data(uploaded_file, downsample_ratio=100):
    """加载CSV或Excel文件（不立即展开列表列）"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("不支持的文件格式，请上传CSV或Excel文件")
            return None, None, False, None
        
        # 只检测列表列，不展开
        list_columns_info = detect_list_columns(df)
        
        # 检查是否为大文件
        is_large = len(df) > LARGE_FILE_THRESHOLD
        
        # 如果是大文件，生成降采样版本（使用简单降采样，因为还不知道要画哪些列）
        downsampled_df = None
        if is_large:
            target_points = max(1000, len(df) // downsample_ratio)  # 根据倍数计算目标点数，最少1000点
            with st.spinner(f"⏳ 检测到大文件 ({len(df):,} 行)，正在生成预览数据（{downsample_ratio}倍降采样到约{target_points:,}点）..."):
                downsampled_df = simple_downsample(df, target_points)
            st.success(f"✅ 预览数据已生成 ({len(downsampled_df):,} 点)")
        
        return df, list_columns_info, is_large, downsampled_df
    except Exception as e:
        st.error(f"读取文件出错: {str(e)}")
        return None, None, False, None

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

def prepare_plot_data(original_df, selections, list_columns_info, data_source=None, 
                      use_downsample=False, x_column=None, y_columns=None,
                      range_start=None, range_end=None, use_index_range=False, downsample_ratio=100):
    """
    准备绘图数据（按需展开列表列，支持降采样和范围过滤）
    
    Args:
        original_df: 原始DataFrame
        selections: 选择字典 {'normal': [...], 'list_columns': {'col': [indices]}}
        list_columns_info: 列表列信息
        data_source: 数据源文件名（用于缓存区分）
        use_downsample: 是否使用降采样
        x_column: X轴列名（用于LTTB降采样）
        y_columns: Y轴列名列表（用于LTTB降采样）
        range_start: 范围起始值（基于x_column的值或行索引）
        range_end: 范围结束值（基于x_column的值或行索引）
        use_index_range: 是否使用行索引范围（当X轴非数值型时）
    
    Returns:
        tuple: (合并后的DataFrame，原始索引列表)
    """
    # 如果指定了范围，先进行范围过滤
    if range_start is not None and range_end is not None:
        if use_index_range:
            # 使用行索引范围
            range_start = int(range_start)
            range_end = int(range_end)
            if range_start >= 0 and range_end < len(original_df) and range_start <= range_end:
                result_df = original_df.iloc[range_start:range_end + 1].copy()
                original_indices = list(range(range_start, range_end + 1))
            else:
                result_df = original_df.copy()
                original_indices = list(range(len(original_df)))
        elif x_column is not None and x_column in original_df.columns:
            # 使用X轴值范围（数值型X轴）
            mask = (original_df[x_column] >= range_start) & (original_df[x_column] <= range_end)
            result_df = original_df[mask].copy()
            original_indices = original_df[mask].index.tolist()
        else:
            result_df = original_df.copy()
            original_indices = list(range(len(original_df)))
    else:
        result_df = original_df.copy()
        original_indices = list(range(len(original_df)))
    
    # 按需展开选中的列表列通道
    for list_col, channel_indices in selections.get('list_columns', {}).items():
        if not channel_indices:
            continue
            
        # 检查缓存（包含数据源信息）
        cache_key = f"{data_source}_{list_col}_{'_'.join(map(str, sorted(channel_indices)))}" if data_source else f"{list_col}_{'_'.join(map(str, sorted(channel_indices)))}"
        if cache_key not in st.session_state.expanded_list_columns:
            # 展开列表列
            expanded_df = expand_list_column_lazy(result_df, list_col, channel_indices, data_source)
            st.session_state.expanded_list_columns[cache_key] = expanded_df
        else:
            expanded_df = st.session_state.expanded_list_columns[cache_key]
            # 如果进行了范围过滤，需要重新提取对应行
            if range_start is not None and range_end is not None:
                expanded_df = expand_list_column_lazy(result_df, list_col, channel_indices, data_source)
        
        # 合并到结果DataFrame
        for col in expanded_df.columns:
            result_df[col] = expanded_df[col]
    
    # 如果使用降采样且数据量大（并且没有指定范围）
    target_points = max(1000, len(result_df) // downsample_ratio)  # 根据倍数计算目标点数
    if use_downsample and len(result_df) > target_points and range_start is None and range_end is None:
        if x_column and y_columns:
            # 检查X轴是否为数值类型
            if x_column in result_df.columns and pd.api.types.is_numeric_dtype(result_df[x_column]):
                # 使用LTTB算法降采样
                result_df = lttb_downsample(result_df, x_column, y_columns, target_points)
                # 更新原始索引以匹配降采样后的数据
                original_indices = result_df.index.tolist()
            else:
                # X轴不是数值类型，使用简单降采样
                result_df = simple_downsample(result_df, target_points)
                # 更新原始索引以匹配降采样后的数据
                original_indices = result_df.index.tolist()
    
    return result_df, original_indices

def create_plotly_chart_overlay(chart_config, data, original_indices=None):
    """创建重叠模式的Plotly图表 - 多条曲线，每条独立Y轴"""
    
    # 获取所有Y列（不区分Y1和Y2）
    all_y_columns = chart_config.get('y1_columns', []) + chart_config.get('y2_columns', [])
    
    if len(all_y_columns) == 0:
        # 没有Y列，返回空图
        return go.Figure(), {}
    
    # 获取配置
    decimal_places = chart_config.get('decimal_places', 4)
    if decimal_places == 0:
        hover_format = ':.0f'
        tick_format = ',.0f'
    else:
        hover_format = f':.{decimal_places}f'
        tick_format = f',.{decimal_places}f'
    
    # 准备行索引数据
    if original_indices is not None:
        row_indices = original_indices
    else:
        row_indices = data.index.tolist()
    
    # 定义高辨识度的颜色序列（最多支持10条曲线）
    color_palette = [
        '#E74C3C',  # 红色
        '#3498DB',  # 蓝色
        '#2ECC71',  # 绿色
        '#F39C12',  # 橙色
        '#9B59B6',  # 紫色
        '#1ABC9C',  # 青色
        '#E67E22',  # 深橙
        '#34495E',  # 深灰蓝
        '#E91E63',  # 粉红
        '#00BCD4',  # 天蓝
    ]
    
    # 创建图表
    fig = go.Figure()
    
    # Y轴布局策略配置
    axis_placement = chart_config.get('axis_placement', 'alternate')  # 'alternate'(左右交替) 或 'left'(左侧堆叠)
    tick_font_size = 9  # 刻度字号
    
    # 自适应轴间距：根据刻度数字最长位数计算
    # 一次性筛选出所有数值型Y列，向量化计算最大绝对值
    numeric_y_cols = [col for col in all_y_columns if col in data.columns and pd.api.types.is_numeric_dtype(data[col])]
    if numeric_y_cols:
        # pandas 向量化操作：一次性计算所有列的绝对值最大值
        max_abs_value = data[numeric_y_cols].abs().max().max()
        if pd.isna(max_abs_value):
            max_abs_value = 0
    else:
        max_abs_value = 0
    
    # 计算整数位数
    if max_abs_value > 0:
        import math
        int_digits = int(math.floor(math.log10(max_abs_value))) + 1
    else:
        int_digits = 1
    
    # 总位数 = 整数位数 + 1(小数点) + 小数位数
    total_digits = int_digits + 1 + decimal_places
    
    # 轴间距 = 位数 * 系数（每位约0.004的宽度）
    axis_offset = total_digits * 0.004 + 0.01  # 基础间距 + 位数相关间距
    
    # 添加每条曲线和对应的Y轴
    for idx, y_col in enumerate(all_y_columns):
        if y_col not in data.columns:
            continue
        
        # 分配颜色
        color = color_palette[idx % len(color_palette)]
        
        # 确定Y轴名称和位置
        if idx == 0:
            yaxis_name = 'y'
            yaxis_ref = 'y'
        else:
            yaxis_name = f'y{idx + 1}'
            yaxis_ref = f'y{idx + 1}'
        
        # 准备数据
        x_data = data[chart_config['x_column']]
        y_data = data[y_col]
        
        # 检测数据类型
        is_numeric = pd.api.types.is_numeric_dtype(y_data)
        if is_numeric:
            y_hover = f'%{{y{hover_format}}}'
        else:
            y_hover = '%{y}'
        
        # Hover模板（只在第一条曲线显示行索引）
        if idx == 0:
            hover_template = f'<b>{y_col}</b>: {y_hover} (行索引: %{{customdata}})<extra></extra>'
        else:
            hover_template = f'<b>{y_col}</b>: {y_hover}<extra></extra>'
        
        # 添加曲线
        if chart_config['chart_type'] == '折线图':
            trace = go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_col,
                yaxis=yaxis_ref,
                line=dict(color=color, width=2),
                customdata=row_indices,
                hovertemplate=hover_template,
                legendgroup=y_col,
            )
        else:  # 散点图
            trace = go.Scattergl(
                x=x_data,
                y=y_data,
                mode='markers',
                name=y_col,
                yaxis=yaxis_ref,
                marker=dict(color=color, size=5),
                customdata=row_indices,
                hovertemplate=hover_template,
                legendgroup=y_col,
            )
        
        fig.add_trace(trace)
    
    # 第一步：统计左右两侧各有多少根轴
    total_count = len([col for col in all_y_columns if col in data.columns])
    
    if axis_placement == 'alternate':
        # 左右交替：左侧=(total+1)//2，右侧=total//2
        left_count = (total_count + 1) // 2
        right_count = total_count // 2
    else:
        # 全部左侧
        left_count = total_count
        right_count = 0
    
    # 计算绘图区边界（先确定绘图区，再由内向外分配轴）
    # 左侧轴区：编号0最靠近绘图区，编号越大越远离绘图区
    # 右侧轴区：编号0最靠近绘图区，编号越大越远离绘图区
    domain_left = left_count * axis_offset if left_count > 0 else 0.02
    domain_right = 1.0 - right_count * axis_offset if right_count > 0 else 0.98
    
    # 第二步：为每根轴分配位置（由内向外编号：0, 1, 2...）
    # 特征分配顺序：第1个→左0，第2个→右0，第3个→左1，第4个→右1...
    axis_positions = []
    left_slot = 0   # 左侧轴区当前槽位（由内向外：0, 1, 2...）
    right_slot = 0  # 右侧轴区当前槽位（由内向外：0, 1, 2...）
    
    for idx, y_col in enumerate(all_y_columns):
        if y_col not in data.columns:
            continue
        
        color = color_palette[idx % len(color_palette)]
        
        # 确定side和slot（由内向外编号）
        if axis_placement == 'alternate':
            # 左右交替布局
            if idx % 2 == 0:
                # 左侧：槽位0在domain_left位置，槽位n在domain_left - n*axis_offset
                side = 'left'
                slot = left_slot
                position = domain_left - slot * axis_offset
                left_slot += 1
            else:
                # 右侧：槽位0在domain_right位置，槽位n在domain_right + n*axis_offset
                side = 'right'
                slot = right_slot
                position = domain_right + slot * axis_offset
                right_slot += 1
        else:
            # 全部左侧堆叠：槽位0在domain_left位置，槽位n在domain_left - n*axis_offset
            side = 'left'
            slot = left_slot
            position = domain_left - slot * axis_offset
            left_slot += 1
        
        # 记录轴信息（slot用于annotation上下交替和位置计算）
        axis_positions.append((idx, side, position, color, y_col, slot))
    
    # 配置X轴
    xaxis_config = {
        'title': {'text': chart_config['x_column']},
        'showgrid': chart_config.get('show_grid', True),
        'showline': True,
        'zeroline': True,
        'fixedrange': False,
        'exponentformat': 'none',
        'separatethousands': True,
        'domain': [domain_left, domain_right]  # 动态计算的作图区域
    }
    
    # 配置所有Y轴（设置空title避免"click to enter"提示）
    layout_update = {'xaxis': xaxis_config}
    annotations = []  # 存储Y轴名称标注
    
    for idx, side, position, color, y_col, slot in axis_positions:
        
        # Y轴配置（设置空title避免"click to enter"提示）
        if idx == 0:
            # 第一个Y轴（主轴）
            yaxis_config = {
                'title': {'text': ''},  # 空title，避免显示"click to enter"
                'tickfont': {'color': color, 'size': tick_font_size},
                'showgrid': chart_config.get('show_grid', True),
                'showline': True,
                'linecolor': color,
                'linewidth': 2,
                'zeroline': False,
                'fixedrange': False,
                'exponentformat': 'none',
                'tickformat': tick_format,
                'side': side,
                'anchor': 'free',  # 使用free才能让position生效
                'position': position
            }
            layout_update['yaxis'] = yaxis_config
        else:
            # 其他Y轴
            yaxis_config = {
                'title': {'text': ''},  # 空title，避免显示"click to enter"
                'tickfont': {'color': color, 'size': tick_font_size},
                'overlaying': 'y',
                'side': side,
                'anchor': 'free',  # 使用free才能让position生效
                'position': position,
                'showgrid': False,
                'showline': True,
                'linecolor': color,
                'linewidth': 2,
                'zeroline': False,
                'fixedrange': False,
                'exponentformat': 'none',
                'tickformat': tick_format
            }
            layout_update[f'yaxis{idx + 1}'] = yaxis_config
        
        # 计算 annotation 的 y 位置（上下交替）
        # slot 是由内向外的编号：0最靠近绘图区，1, 2, 3...
        # 偶数slot（0, 2, 4...）在上方，奇数slot（1, 3, 5...）在下方
        if slot % 2 == 0:
            annotation_y = 1.02
            annotation_yanchor = 'bottom'
        else:
            annotation_y = -0.02
            annotation_yanchor = 'top'
        
        # 添加Y轴名称标注
        annotations.append(dict(
            x=position,  # 直接使用轴的position，在轴正上方/正下方
            y=annotation_y,
            xref='paper',
            yref='paper',
            text=y_col,
            showarrow=False,
            font=dict(color=color, size=10),
            xanchor='center',  # 居中对齐
            yanchor=annotation_yanchor
        ))
    
    # 设置整体布局
    fig.update_layout(
        title={
            'text': chart_config['title'],
            'xanchor': 'left',
            'x': 0
        },
        hovermode='x unified',  # 统一显示所有曲线的值
        width=chart_config.get('width', 1200),
        height=chart_config['height'],
        showlegend=True,
        legend={
            'orientation': 'h',  # 横向排列
            'yanchor': 'bottom',
            'y': 1.02,  # 放在图上方
            'xanchor': 'center',
            'x': 0.5,  # 居中
            'font': {'size': 11},
            'bgcolor': 'rgba(255, 255, 255, 0)',  # 透明背景
            'bordercolor': 'rgba(0, 0, 0, 0)'  # 透明边框
        },
        dragmode='zoom',
        annotations=annotations,  # 添加Y轴名称标注
        **layout_update
    )
    
    # 配置交互选项
    config = {
        'scrollZoom': True,
        'displayModeBar': True,
        'displaylogo': False,
        'editable': True,
        'edits': {
            'titleText': True,
            'axisTitleText': False,  # 禁止编辑Y轴标题，避免误触
        }
    }
    
    return fig, config


def create_plotly_chart(chart_config, data, original_indices=None):
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
    
    # 准备行索引数据（如果提供）
    if original_indices is not None:
        row_indices = original_indices
    else:
        row_indices = data.index.tolist()
    
    # 添加Y1轴的曲线
    is_first_trace = True
    for y_col in y1_columns:
        if y_col not in data.columns:
            continue
            
        x_data = data[chart_config['x_column']]
        y_data = data[y_col]
        
        # 检测y数据类型，如果是字符串类型则不使用数值格式化
        is_numeric = pd.api.types.is_numeric_dtype(y_data)
        if is_numeric:
            y_hover = f'%{{y{hover_format}}}'
        else:
            y_hover = '%{y}'
        
        # 第一个 trace 显示行索引
        if is_first_trace:
            hover_template = f'<b>{y_col}</b>: {y_hover} (行索引: %{{customdata}})<extra></extra>'
            is_first_trace = False
        else:
            hover_template = f'<b>{y_col}</b>: {y_hover}<extra></extra>'
        
        if chart_config['chart_type'] == '折线图':
            trace = go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_col,
                yaxis='y',
                customdata=row_indices,
                hovertemplate=hover_template
            )
        else:  # 散点图 - 使用Scattergl提升性能
            trace = go.Scattergl(
                x=x_data,
                y=y_data,
                mode='markers',
                name=y_col,
                yaxis='y',
                customdata=row_indices,
                hovertemplate=hover_template
            )
        
        fig.add_trace(trace)
    
    # 添加Y2轴的曲线
    for y_col in y2_columns:
        if y_col not in data.columns:
            continue
            
        x_data = data[chart_config['x_column']]
        y_data = data[y_col]
        
        # 检测y数据类型，如果是字符串类型则不使用数值格式化
        is_numeric = pd.api.types.is_numeric_dtype(y_data)
        if is_numeric:
            y_hover = f'%{{y{hover_format}}}'
        else:
            y_hover = '%{y}'
        
        # 如果 Y1 为空，在第一个 Y2 trace 显示行索引
        if is_first_trace:
            hover_template = f'<b>{y_col}</b>: {y_hover} (行索引: %{{customdata}})<extra></extra>'
            is_first_trace = False
        else:
            hover_template = f'<b>{y_col}</b>: {y_hover}<extra></extra>'
        
        if chart_config['chart_type'] == '折线图':
            trace = go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_col,
                yaxis='y2',
                customdata=row_indices,
                hovertemplate=hover_template
            )
        else:  # 散点图 - 使用Scattergl提升性能
            trace = go.Scattergl(
                x=x_data,
                y=y_data,
                mode='markers',
                name=y_col,
                yaxis='y2',
                customdata=row_indices,
                hovertemplate=hover_template
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
            'orientation': 'h',  # 横向排列
            'yanchor': 'bottom',
            'y': 1.02,  # 放在图上方
            'xanchor': 'center',
            'x': 0.5  # 居中
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
        'editable': True,  # 启用标题编辑
        'edits': {
            'titleText': True,  # 可编辑图表标题
            'axisTitleText': True,  # 可编辑坐标轴标题
        }
    }
    
    return fig, config

def create_plotly_histogram(chart_config, data, chart_idx):
    """创建直方图，支持多特征叠加显示"""
    
    # 获取所有Y列（直方图模式下不区分Y1和Y2）
    all_y_columns = chart_config.get('y1_columns', []) + chart_config.get('y2_columns', [])
    
    if len(all_y_columns) == 0:
        return go.Figure(), {}
    
    # 获取配置
    decimal_places = chart_config.get('decimal_places', 4)
    num_bins = chart_config.get('histogram_bins', 50)
    hist_normalize = chart_config.get('hist_normalize', False)
    
    # 根据小数位数生成格式字符串
    if decimal_places == 0:
        hover_format = ':.0f'
    else:
        hover_format = f':.{decimal_places}f'
    
    # 定义高辨识度的颜色序列
    color_palette = [
        '#E74C3C',  # 红色
        '#3498DB',  # 蓝色
        '#2ECC71',  # 绿色
        '#F39C12',  # 橙色
        '#9B59B6',  # 紫色
        '#1ABC9C',  # 青色
        '#E67E22',  # 深橙
        '#34495E',  # 深灰蓝
        '#E91E63',  # 粉红
        '#00BCD4',  # 天蓝
    ]
    
    # 计算透明度：多个特征时自动调整透明度
    num_features = len([col for col in all_y_columns if col in data.columns])
    if num_features <= 1:
        opacity = 0.75
    elif num_features == 2:
        opacity = 0.6
    elif num_features <= 4:
        opacity = 0.5
    elif num_features <= 6:
        opacity = 0.4
    else:
        opacity = 0.35
    
    # 创建图表
    fig = go.Figure()
    
    # 收集所有数据的范围，用于统一bin范围
    all_data_min = float('inf')
    all_data_max = float('-inf')
    valid_columns = []
    
    for y_col in all_y_columns:
        if y_col not in data.columns:
            continue
        y_data = data[y_col].dropna()
        if len(y_data) == 0:
            continue
        if not pd.api.types.is_numeric_dtype(y_data):
            continue
        valid_columns.append(y_col)
        all_data_min = min(all_data_min, y_data.min())
        all_data_max = max(all_data_max, y_data.max())
    
    if len(valid_columns) == 0:
        st.warning("⚠️ 没有可绘制的数值型列")
        return go.Figure(), {}
    
    # 计算bin大小
    data_range = all_data_max - all_data_min
    if data_range == 0:
        data_range = 1
    bin_size = data_range / num_bins
    
    # 添加每个特征的直方图
    for idx, y_col in enumerate(valid_columns):
        color = color_palette[idx % len(color_palette)]
        y_data = data[y_col].dropna()
        
        # 归一化模式
        histnorm = 'probability density' if hist_normalize else None
        
        # Hover模板
        if hist_normalize:
            hover_template = f'<b>{y_col}</b><br>范围: %{{x}}<br>概率密度: %{{y{hover_format}}}<extra></extra>'
        else:
            hover_template = f'<b>{y_col}</b><br>范围: %{{x}}<br>频数: %{{y}}<extra></extra>'
        
        fig.add_trace(go.Histogram(
            x=y_data,
            name=y_col,
            opacity=opacity,
            marker=dict(color=color, line=dict(color='white', width=0.5)),
            xbins=dict(
                start=all_data_min,
                end=all_data_max,
                size=bin_size
            ),
            histnorm=histnorm,
            hovertemplate=hover_template
        ))
    
    # 多特征时使用overlay模式
    barmode = 'overlay' if len(valid_columns) > 1 else 'relative'
    
    # Y轴标题
    y_title = '概率密度' if hist_normalize else '频数'
    
    # 设置布局
    fig.update_layout(
        title={
            'text': chart_config['title'],
            'xanchor': 'left',
            'x': 0
        },
        xaxis=dict(
            title=dict(text='数值范围'),
            showgrid=chart_config.get('show_grid', True),
            showline=True,
            zeroline=True,
            fixedrange=False,
            exponentformat='none',
            separatethousands=True
        ),
        yaxis=dict(
            title=dict(text=y_title),
            showgrid=chart_config.get('show_grid', True),
            showline=True,
            zeroline=True,
            fixedrange=False,
            exponentformat='none'
        ),
        barmode=barmode,
        width=chart_config.get('width', 1200),
        height=chart_config['height'],
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        ),
        dragmode='zoom',
        hovermode='x unified'
    )
    
    # 配置交互选项 - 启用滚轮缩放以调整bin大小
    config = {
        'scrollZoom': True,
        'displayModeBar': True,
        'displaylogo': False,
        'editable': True,
        'edits': {
            'titleText': True,
            'axisTitleText': True,
        }
    }
    
    # 存储当前bin信息到session state，用于滚轮调整
    st.session_state.histogram_bins[chart_idx] = num_bins
    
    return fig, config


def render_histogram_bin_control(idx, chart_config):
    """渲染直方图的bin控制组件（放在图表下方）"""
    st.markdown("##### 🎚️ 直方图分箱控制")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        current_bins = st.session_state.histogram_bins.get(idx, chart_config.get('histogram_bins', 50))
        new_bins = st.slider(
            "分箱数 (Bins)",
            min_value=5,
            max_value=500,
            value=current_bins,
            step=1,
            key=f"hist_bins_control_{idx}",
            help="调整直方图的分箱数量，数值越大柱子越细"
        )
        
        if new_bins != current_bins:
            st.session_state.histogram_bins[idx] = new_bins
            # 同时更新图表配置
            st.session_state.charts[idx]['histogram_bins'] = new_bins
            st.rerun()
    
    with col2:
        # 快捷按钮
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
        with btn_col1:
            if st.button("➖", key=f"bins_dec_{idx}", help="减少分箱数"):
                new_val = max(5, current_bins - 5)
                st.session_state.histogram_bins[idx] = new_val
                st.session_state.charts[idx]['histogram_bins'] = new_val
                st.rerun()
        with btn_col2:
            if st.button("➕", key=f"bins_inc_{idx}", help="增加分箱数"):
                new_val = min(500, current_bins + 5)
                st.session_state.histogram_bins[idx] = new_val
                st.session_state.charts[idx]['histogram_bins'] = new_val
                st.rerun()
        with btn_col3:
            if st.button("½", key=f"bins_half_{idx}", help="分箱数减半"):
                new_val = max(5, current_bins // 2)
                st.session_state.histogram_bins[idx] = new_val
                st.session_state.charts[idx]['histogram_bins'] = new_val
                st.rerun()
        with btn_col4:
            if st.button("2×", key=f"bins_double_{idx}", help="分箱数加倍"):
                new_val = min(500, current_bins * 2)
                st.session_state.histogram_bins[idx] = new_val
                st.session_state.charts[idx]['histogram_bins'] = new_val
                st.rerun()
    
    with col3:
        st.caption(f"当前: {current_bins} bins")


# 主标题
st.title("📊 交互式绘图工具")
st.markdown("---")

# 侧边栏：文件上传
with st.sidebar:
    st.header("📁 数据加载")
    
    uploaded_files = st.file_uploader(
        "上传CSV或Excel文件（可多选）",
        type=['csv', 'xlsx', 'xls'],
        help="选择一个或多个数据文件，第一行应为列名",
        accept_multiple_files=True
    )
    
    if uploaded_files:
        # 处理新上传的文件
        current_filenames = {f.name for f in uploaded_files}
        existing_filenames = set(st.session_state.files_data.keys())
        
        # 添加新文件
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in existing_filenames:
                data, list_columns_info, is_large, downsampled_df = load_data(uploaded_file, st.session_state.downsample_ratio)
                if data is not None:
                    st.session_state.files_data[uploaded_file.name] = {
                        'data': data,
                        'list_columns_info': list_columns_info,
                        'is_large': is_large,
                        'downsampled': downsampled_df
                    }
        
        # 删除已移除的文件
        files_to_remove = existing_filenames - current_filenames
        for filename in files_to_remove:
            del st.session_state.files_data[filename]
            
            # 清理该文件相关的所有缓存
            # 1. 清理解析缓存
            keys_to_delete = [key for key in st.session_state.parsed_list_columns.keys() 
                            if key.startswith(f"{filename}_")]
            for key in keys_to_delete:
                del st.session_state.parsed_list_columns[key]
            
            # 2. 清理展开缓存
            keys_to_delete = [key for key in st.session_state.expanded_list_columns.keys() 
                            if key.startswith(f"{filename}_")]
            for key in keys_to_delete:
                del st.session_state.expanded_list_columns[key]
            
            # 3. 清理使用该文件的图表配置和相关状态
            charts_to_reset = []
            for idx, chart in enumerate(st.session_state.charts):
                if chart.get('data_source') == filename:
                    charts_to_reset.append(idx)
            
            for idx in charts_to_reset:
                # 重置图表配置
                st.session_state.charts[idx]['data_source'] = None
                st.session_state.charts[idx]['is_configured'] = False
                st.session_state.charts[idx]['y1_columns'] = []
                st.session_state.charts[idx]['y2_columns'] = []
                
                # 清理该图表的所有相关状态
                clear_chart_states(idx)
        
        # 显示已加载的文件
        if st.session_state.files_data:
            st.success(f"✅ 已加载 {len(st.session_state.files_data)} 个文件")
            
            # 显示每个文件的信息
            for filename, file_info in st.session_state.files_data.items():
                # 为大文件添加标记
                file_display = f"📄 {filename}"
                if file_info.get('is_large', False):
                    file_display = f"📦 {filename} (大文件)"
                
                with st.expander(file_display):
                    data = file_info['data']
                    list_columns_info = file_info['list_columns_info']
                    is_large = file_info.get('is_large', False)
                    
                    if is_large:
                        st.info(f"📊 数据形状: {data.shape[0]:,} 行 × {data.shape[1]} 列 (已启用降采样优化)")
                    else:
                        st.info(f"数据形状: {data.shape[0]:,} 行 × {data.shape[1]} 列")
                    
                    # 显示列表列信息
                    if list_columns_info:
                        st.markdown("**📊 列表列:**")
                        for col_name, info in list_columns_info.items():
                            st.write(f"- {col_name} → {info['num_channels']} 个通道")
                    
                    # 显示数据预览
                    st.markdown("**📋 数据预览:**")
                    st.dataframe(data.head(5), use_container_width=True)
                    
                    # 删除单个文件按钮
                    if st.button(f"🗑️ 删除文件", key=f"delete_file_{filename}"):
                        del st.session_state.files_data[filename]
                        
                        # 清理该文件相关的所有缓存
                        # 1. 清理解析缓存
                        keys_to_delete = [key for key in st.session_state.parsed_list_columns.keys() 
                                        if key.startswith(f"{filename}_")]
                        for key in keys_to_delete:
                            del st.session_state.parsed_list_columns[key]
                        
                        # 2. 清理展开缓存
                        keys_to_delete = [key for key in st.session_state.expanded_list_columns.keys() 
                                        if key.startswith(f"{filename}_")]
                        for key in keys_to_delete:
                            del st.session_state.expanded_list_columns[key]
                        
                        # 3. 清理使用该文件的图表配置和相关状态
                        charts_to_reset = []
                        for idx, chart in enumerate(st.session_state.charts):
                            if chart.get('data_source') == filename:
                                charts_to_reset.append(idx)
                        
                        for idx in charts_to_reset:
                            # 重置图表配置
                            st.session_state.charts[idx]['data_source'] = None
                            st.session_state.charts[idx]['is_configured'] = False
                            st.session_state.charts[idx]['y1_columns'] = []
                            st.session_state.charts[idx]['y2_columns'] = []
                            
                            # 清理该图表的所有相关状态
                            clear_chart_states(idx)
                        
                        st.rerun()
    else:
        # 清空所有数据
        if st.session_state.files_data:
            # 清理所有图表的状态
            for idx in range(len(st.session_state.charts)):
                clear_chart_states(idx)
            
            st.session_state.files_data = {}
            st.session_state.charts = []
            st.session_state.edit_mode = {}
            st.session_state.expanded_list_columns = {}
            st.session_state.parsed_list_columns = {}
            st.session_state.confirm_clear = False

# 添加图表到列表的回调函数
def add_new_chart(position=None):
    """添加新图表，position为None表示添加到末尾，否则插入到指定位置后"""
    # 如果只有一个文件，自动选择；否则留空
    filenames = list(st.session_state.files_data.keys())
    default_data_source = filenames[0] if len(filenames) == 1 else None
    
    # 获取默认x_column
    default_x_column = ''
    if default_data_source:
        data = st.session_state.files_data[default_data_source]['data']
        default_x_column = data.columns[0] if len(data.columns) > 0 else ''
    
    new_chart = {
        'title': f"图表 {len(st.session_state.charts) + 1}",
        'chart_type': '折线图',
        'data_source': default_data_source,  # 数据来源文件名
        'x_column': default_x_column,
        'y1_columns': [],
        'y2_columns': [],
        'show_grid': True,
        'width': 2000,  # 图表宽度
        'height': 500,
        'decimal_places': 2,
        'overlay_mode': False,  # 重叠模式开关
        'axis_placement': 'alternate',  # Y轴排布策略：'alternate'(左右交替) 或 'left'(左侧堆叠)
        'is_configured': False,  # 标记图表是否已配置
        'use_downsample': True,  # 默认使用降采样（如果是大文件）
        'range_start': None,  # 范围起始
        'range_end': None  # 范围结束
    }
    if position is None:
        st.session_state.charts.append(new_chart)
        new_idx = len(st.session_state.charts) - 1
    else:
        st.session_state.charts.insert(position + 1, new_chart)
        new_idx = position + 1
    st.session_state.edit_mode[new_idx] = True  # 新图表默认打开编辑模式
    
    # 初始化图表的范围模式（根据数据源决定，大文件默认降采样，否则默认原始数据）
    # 注意：此时可能还没有选择数据源，所以先不初始化，等选择数据源后再初始化
    st.session_state.chart_range_selection[new_idx] = None

# 渲染单个图表区域
def render_chart_area(idx, chart_config):
    """渲染单个图表区域，包括属性面板和图表显示"""
    
    # 使用容器包裹整个图表区域
    with st.container():
        # 标题栏和操作按钮
        col_title, col_edit, col_delete = st.columns([5, 1.5, 1.5])
        with col_title:
            # 显示图表标题和数据来源
            data_source_tag = f" [{chart_config.get('data_source', '未选择')}]" if len(st.session_state.files_data) > 1 else ""
            st.subheader(f"{idx + 1}. {chart_config['title']}{data_source_tag}")
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
        
        # 属性编辑面板（仅在编辑模式下显示）- 使用 fragment 避免属性修改时刷新整个页面
        if st.session_state.edit_mode.get(idx, False):
            render_chart_properties_fragment(idx, chart_config)
            
            # 属性和图表之间的虚线分隔
            st.markdown('<div class="property-separator"></div>', unsafe_allow_html=True)
        
        # 图表显示区域
        if chart_config['is_configured'] and (chart_config.get('y1_columns') or chart_config.get('y2_columns')):
            # 获取数据源
            data_source = chart_config.get('data_source')
            if not data_source or data_source not in st.session_state.files_data:
                st.error(f"❌ 数据源 '{data_source}' 不存在！请重新配置图表。")
                return
            
            try:
                # 获取对应的数据和列表列信息
                file_info = st.session_state.files_data[data_source]
                original_data = file_info['data']
                list_columns_info = file_info['list_columns_info']
                is_large_file = file_info.get('is_large', False)
                
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
                
                # 原始数据模式下的范围选择（仅在大文件且选择原始数据模式时显示）
                current_display_mode = st.session_state.chart_range_mode.get(idx, 'original')
                if is_large_file and current_display_mode == 'original' and not st.session_state.chart_data_ready.get(idx, True):
                    st.markdown("##### 📍 选择数据范围")
                    
                    # 三向联动：降采样图行号 ↔ 原始数据行号 ↔ 百分比
                    st.caption("💡 从降采样图的hover中读取行索引，或直接填写百分比/原始行号，三者自动联动")
                    
                    x_col = chart_config.get('x_column')
                    if x_col and x_col in original_data.columns:
                        total_rows = len(original_data)
                        downsampled_rows = max(1000, total_rows // st.session_state.downsample_ratio)
                        
                        # 如果还没有设置范围，使用默认值（中间20%）
                        if idx not in st.session_state.chart_range_selection or st.session_state.chart_range_selection[idx] is None:
                            is_numeric_x = pd.api.types.is_numeric_dtype(original_data[x_col])
                            if is_numeric_x:
                                x_min = float(original_data[x_col].min())
                                x_max = float(original_data[x_col].max())
                                x_range = x_max - x_min
                                range_start = x_min + x_range * 0.4
                                range_end = x_min + x_range * 0.6
                            else:
                                range_start = int(total_rows * 0.4)
                                range_end = int(total_rows * 0.6)
                            st.session_state.chart_range_selection[idx] = (range_start, range_end)
                        
                        # 使用 fragment 渲染输入控件
                        render_range_input_controls(idx, total_rows, downsampled_rows, x_col, original_data)
                    
                    st.markdown("---")
                    
                    # 绘制按钮
                    col_btn1, col_btn2 = st.columns([1, 3])
                    with col_btn1:
                        if st.button("🎨 绘制原始数据图表", key=f"draw_original_{idx}", type="primary", use_container_width=True):
                            st.session_state.confirmed_chart_range[idx] = st.session_state.chart_range_selection.get(idx)
                            st.session_state.chart_data_ready[idx] = True
                            st.rerun()
                    with col_btn2:
                        st.caption("💡 点击按钮后将加载并绘制选定范围的原始数据")
                    
                    st.markdown("---")
                    st.info("💡 下方仍显示降采样预览图，配置好范围后点击「绘制原始数据图表」按钮查看精确数据")
                
                # 确定应该显示哪种数据
                show_downsampled = False  # 是否显示降采样数据
                show_original = False     # 是否显示原始数据
                
                if current_display_mode == 'downsampled':
                    # 降采样模式：显示降采样数据
                    show_downsampled = True
                else:  # 原始数据模式
                    if st.session_state.chart_data_ready.get(idx, True):
                        # 已准备好：显示原始数据
                        show_original = True
                    else:
                        # 大文件未确认范围：继续显示降采样图
                        show_downsampled = True
                
                if not show_downsampled and not show_original:
                    # 不应该发生，但作为安全措施
                    st.warning("⚠️ 无法确定显示模式")
                else:
                    # 根据显示模式准备数据
                    use_downsample = False
                    range_start = None
                    range_end = None
                    use_index_range = False
                    
                    if show_downsampled:
                        # 显示降采样数据
                        use_downsample = True
                    elif show_original:
                        # 显示原始数据
                        # 使用已确认的范围（点击绘制按钮时保存的），而不是当前输入框的值
                        if is_large_file and idx in st.session_state.confirmed_chart_range and st.session_state.confirmed_chart_range[idx]:
                            # 大文件且有已确认的范围选择：使用范围过滤
                            range_start, range_end = st.session_state.confirmed_chart_range[idx]
                            
                            # 检查X轴是否为数值类型，决定使用值范围还是索引范围
                            x_col = chart_config.get('x_column')
                            if x_col and x_col in original_data.columns:
                                use_index_range = not pd.api.types.is_numeric_dtype(original_data[x_col])
                
                    # 获取所有Y轴列名（用于LTTB降采样）
                    all_y_columns = chart_config.get('y1_columns', []) + chart_config.get('y2_columns', [])
                    
                    # 准备完整的数据
                    plot_data, original_indices = prepare_plot_data(
                        original_data, 
                        all_selections, 
                        list_columns_info, 
                        data_source,
                        use_downsample=use_downsample,
                        x_column=chart_config.get('x_column'),
                        y_columns=all_y_columns,
                        range_start=range_start,
                        range_end=range_end,
                        use_index_range=use_index_range,
                        downsample_ratio=st.session_state.downsample_ratio
                    )
                    
                    # 显示实际绘图数据量
                    if show_downsampled and is_large_file:
                        st.success(f"✅ 已加载降采样数据：{len(plot_data):,} 点 (原始: {len(original_data):,} 行)")
                    elif show_original and is_large_file:
                        status_col, btn_col = st.columns([3, 1])
                        with status_col:
                            if range_start is not None and range_end is not None:
                                st.success(f"✅ 已加载原始数据：{len(plot_data):,} 点 (范围内)")
                            else:
                                st.success(f"✅ 已加载原始数据：{len(plot_data):,} 点 (全部)")
                        with btn_col:
                            if st.button("🔄 重新配置", key=f"reconfig_{idx}", use_container_width=True):
                                st.session_state.chart_data_ready[idx] = False
                                st.rerun()
                    
                    # 创建图表（根据模式选择函数）
                    if chart_config.get('chart_type') == '直方图':
                        # 直方图模式
                        fig, config = create_plotly_histogram(chart_config, plot_data, idx)
                    elif chart_config.get('overlay_mode', False):
                        # 重叠模式
                        fig, config = create_plotly_chart_overlay(chart_config, plot_data, original_indices)
                    else:
                        # 普通模式
                        fig, config = create_plotly_chart(chart_config, plot_data, original_indices)
                    
                    # 提示信息
                    if chart_config.get('chart_type') == '直方图':
                        # 直方图的提示
                        st.caption("💡 直方图提示：可框选区域放大；使用下方滑块或快捷按钮调整分箱数；多个特征会叠加显示并自动调整透明度。")
                    elif chart_config.get('overlay_mode', False):
                        # 重叠模式的提示
                        st.caption("💡 重叠模式提示：每条曲线使用独立的Y轴刻度（颜色关联）；可框选区域放大；鼠标悬停在Y轴上滚动滚轮可缩放该轴；双击Y轴自动适配；点击图例可隐藏/显示对应曲线。")
                    elif show_downsampled and is_large_file:
                        if st.session_state.chart_range_mode.get(idx) == 'downsampled':
                            st.caption("💡 提示：当前为降采样预览模式。鼠标悬停查看数据点和行索引；框选放大可查看细节；切换到原始数据模式可加载精确数据。")
                        else:
                            st.caption("💡 提示：下方显示降采样预览图（用于参考）。鼠标悬停查看数据点和行索引；配置好范围后点击「绘制原始数据图表」查看精确数据。")
                    elif show_original:
                        st.caption("💡 提示：可框选区域进行放大；鼠标悬停查看数据点和原始行索引；鼠标悬停在坐标轴上可拖动，滚动滚轮可进行缩放；双击可重置视图。")
                    
                    # 显示图表
                    st.plotly_chart(fig, use_container_width=False, config=config, key=f"chart_{idx}")
                    
                    # 直方图的bin控制组件（放在图表下方）
                    if chart_config.get('chart_type') == '直方图':
                        render_histogram_bin_control(idx, chart_config)
            except Exception as e:
                st.error(f"绘制图表出错: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
        else:
            # 未配置时显示提示
            st.info("👆 请在上方编辑属性并点击「应用修改」来绘制图表")

# 主界面
if st.session_state.files_data:
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
            render_chart_area(idx, chart_config)
            
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
    - ✅ **多文件支持**：可同时加载多个数据文件，每个图表独立选择数据源
    - ✅ **📊 直方图功能（新）**：支持多特征叠加显示，自动调节透明度，可动态调整分箱数
    - ✅ **🎨 重叠模式**：多特征共享X轴，每个特征独立Y轴，颜色强关联（曲线-轴-图例同色）
    - ✅ **Y轴智能排布**：支持左右交替或左侧堆叠两种布局，避免轴标签重叠
    - ✅ **大文件智能优化**：超过50万行数据自动启用降采样，快速预览整体曲线
    - ✅ **双模式显示**：大文件支持降采样预览和原始数据精细查看两种模式
    - ✅ **范围选择加载**：可选定横轴范围，仅加载该范围内的原始颗粒度数据
    - ✅ **LTTB降采样算法**：智能保留数据特征，确保降采样后曲线形态不失真，自动处理非数值数据
    - ✅ **自动解析列表列**：支持字符串形式的列表数据（如 "[2, 5, 8]"），自动展开为多个通道
    - ✅ **智能通道管理**：列表列自动分组显示，可选择性绘制指定通道
    - ✅ 交互式折线图和散点图
    - ✅ 自由选择X轴和多个Y轴列
    - ✅ **下拉勾选式列选择**：改进的列选择器，选中后保持可见
    - ✅ 独立的Y1轴（左侧）和Y2轴（右侧）（普通模式）
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
    1. **上传数据**: 在左侧上传一个或多个数据文件（CSV或Excel），可同时选择多个文件
    2. **创建图表**: 点击虚线框"新增绘图"按钮
    3. **选择数据源**（多文件时）: 如果上传了多个文件，首先选择该图表使用的数据文件
    4. **编辑属性**: 
       - 在属性面板中设置图表标题、类型
       - 选择X轴列
       - 在Y1轴和Y2轴框中选择要显示的列
       - 选择数值小数位数（0-6位）
       - 配置其他选项（网格、高度等）
    5. **应用配置**: 点击「✅ 应用修改」按钮，图表将在当前区域绘制
    6. **继续添加**: 点击图表下方的虚线框"新增绘图"创建更多图表
    7. **修改图表**: 随时点击「⚙️ 编辑属性」重新调整，应用后在同一区域更新
    
    ### 多文件管理
    - **上传多文件**: 在文件上传器中可同时选择多个文件，或分批添加
    - **查看文件信息**: 左侧边栏展开每个文件可查看数据预览和列表列信息
    - **删除单个文件**: 每个文件下方有独立的删除按钮
    - **自动选择数据源**: 
      - 只有1个文件时，新建图表自动选择该文件作为数据源
      - 有多个文件时，需要手动为每个图表选择数据源
    - **数据源显示**: 有多个文件时，图表标题后会显示数据源文件名标签
    
    ### 🎨 重叠模式（多特征独立Y轴）
    当多个特征的量纲和数值范围差异很大时（如温度、压力、速度等），传统的双Y轴不够用。**重叠模式**让你可以在同一张图中绘制任意多个特征，每个特征都有独立的Y轴刻度。
    
    **核心特性：**
    - **颜色强关联**：每条曲线、对应的Y轴刻度、图例文字使用相同的高辨识度颜色（最多支持10种颜色）
    - **Y轴智能排布**：
      - **左右交替**（推荐）：Y轴在左右两侧交替排列，充分利用空间
      - **左侧堆叠**：所有Y轴在左侧排列，适合需要集中查看的场景
    - **统一crosshair**：鼠标悬停时，垂直虚线贯穿所有曲线，tooltip同时显示所有特征值
    - **独立缩放**：鼠标悬停在某个Y轴上滚动滚轮，只缩放该轴对应的曲线
    - **自动适配**：双击某个Y轴，该曲线自动适配到最佳显示范围
    
    **使用方法：**
    1. 在属性面板中勾选「🔄 启用重叠模式」
    2. 选择Y轴排布策略（左右交替 或 左侧堆叠）
    3. 在「Y轴特征」中选择要对比的多个特征（建议不超过10个）
    4. 点击「✅ 应用修改」查看效果
    
    **适用场景：**
    - ✅ 多传感器数据对比（温度、压力、流量等不同量纲）
    - ✅ 多通道信号分析（不同幅值范围的信号）
    - ✅ 多指标趋势对比（销量、利润率、库存等）
    - ✅ 时序数据的多维度观察
    
    **交互提示：**
    - 点击图例可隐藏/显示对应曲线
    - 框选区域可放大X轴范围（所有曲线同步）
    - 鼠标悬停在Y轴上滚轮缩放该轴（曲线上下拉伸）
    - 双击Y轴自动适配该曲线到合适范围
    - 双击图表区域重置所有视图
    
    ### 📊 直方图功能
    直方图用于展示数据的分布情况，支持多个特征的叠加对比。
    
    **核心特性：**
    - **多特征叠加**：可以同时绘制多个特征的直方图，便于对比分布差异
    - **智能透明度**：根据特征数量自动调整柱子透明度，确保重叠部分清晰可见
    - **动态分箱控制**：通过滑块或快捷按钮实时调整分箱数（Bins）
    - **统一范围**：多个特征使用统一的数据范围，便于直观对比
    - **归一化显示**：可选择显示频数或概率密度
    - **列表列支持**：完全支持列表列的通道选择功能
    
    **使用方法：**
    1. 在图表类型中选择「直方图」
    2. 设置初始分箱数（可选）
    3. 选择是否归一化显示
    4. 在「Y轴特征」中选择要分析的一个或多个特征
    5. 点击「✅ 应用修改」查看直方图
    6. 使用图表下方的控制组件实时调整分箱数
    
    **分箱控制：**
    - **滑块**：拖动滑块精确调整分箱数（5-500）
    - **➖ / ➕**：每次增减5个分箱
    - **½**：分箱数减半（柱子变粗）
    - **2×**：分箱数加倍（柱子变细）
    
    **适用场景：**
    - ✅ 数据分布分析（正态、偏态、双峰等）
    - ✅ 异常值检测（查看数据尾部分布）
    - ✅ 多特征分布对比
    - ✅ 数据质量检查（查看数据集中度）
    
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
    
    ### 大文件智能优化 🚀
    - **自动检测**：系统自动识别超过50万行的大文件，并标记为"大文件"
    - **降采样预览模式**：
      - 使用LTTB算法智能降采样到约10,000点
      - 保留数据的主要特征和趋势
      - 快速显示全局曲线样貌，无需等待（1-3秒）
      - 自动检测数据类型，非数值型X轴自动回退到简单采样
    - **原始数据模式**：
      - 可选择横轴的特定范围
      - 仅加载该范围内的原始颗粒度数据
      - 确保局部细节的精确显示
    - **模式切换**：
      - 📉 降采样预览：快速查看全局趋势（约10,000点）
      - 📊 原始数据：精细查看特定区间（完整颗粒度）
    - **使用建议**：
      1. 先用降采样模式快速浏览全局（100万行 → 10,000点，秒级加载）
      2. 发现感兴趣的区域后，切换到原始数据模式
      3. 设置横轴范围，加载该区域的高精度数据
      4. 可根据需要反复切换和调整范围
    - **智能容错**：
      - X轴必须是数值型才能使用LTTB算法
      - 非数值型数据自动使用简单均匀采样
      - 完善的错误处理，确保稳定性
    
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
    - 🚀 **大文件优化**：超过50万行自动启用降采样，先看全局再看细节
    - 🚀 **LTTB算法**：降采样保留数据特征，曲线形态几乎无损，自动处理非数值数据
    - 🚀 **灵活切换**：降采样和原始数据模式可随时切换，满足不同需求
    - 🚀 **智能容错**：X轴非数值型自动回退到简单采样，确保系统稳定运行
    """)

# 页脚
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>交互式绘图工具 v2.3 (直方图 + 重叠模式 + 多Y轴独立刻度) | Developer: yinmingxin</div>",
    unsafe_allow_html=True
)

# 直接运行支持
if __name__ == "__main__":
    try:
        # 检查是否在streamlit运行时环境中
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            # 不在streamlit中，启动streamlit
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
    except:
        # 如果导入失败或其他错误，启动streamlit
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])

