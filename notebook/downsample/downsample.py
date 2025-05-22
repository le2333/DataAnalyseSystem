import lttbc
import numpy as np
import pandas as pd

def lttb(data, threshold=1000):
    """
    使用lttbc库对原始数据进行LTTB降采样

    参数:
        data: DataFrame，index为时间戳，只有一列数据
        threshold: 降采样后点数

    返回:
        降采样后的DataFrame，index和原始数据类型一致
    """
    col = data.columns[0]
    x = np.arange(len(data))  # 用顺序编号做x
    y = data[col].values

    # lttbc.downsample要求x和y为一维数组
    nx, ny = lttbc.downsample(x, y, threshold)

    # nx是降采样后x的下标（浮点型），需要四舍五入转为int
    nx = np.round(nx).astype(int)
    # 防止越界
    nx = np.clip(nx, 0, len(data)-1)

    # 取出原始index和列名
    new_index = data.index[nx]
    result = pd.DataFrame({col: ny}, index=new_index)
    
    print(f"原始数据点数: {len(data)}, 处理后数据点数: {len(result)}")
    
    return result