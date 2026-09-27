"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import access as router_access
from app.routers import plant as router_plant
from app.routers import inspection as router_inspection
from app.routers import panel_clean as router_panel_clean
from app.routers import inverter as router_inverter
from app.routers import power_data as router_power_data
from app.routers import fault as router_fault
from app.routers import spare_part as router_spare_part
from app.routers import transformer as router_transformer
from app.routers import switchgear as router_switchgear
from app.routers import meter as router_meter
from app.routers import weather as router_weather
from app.routers import grid_connect as router_grid_connect
from app.routers import cable as router_cable
from app.routers import security as router_security
from app.routers import maintenance as router_maintenance
from app.routers import dc_box as router_dc_box
from app.routers import energy_saving as router_energy_saving
from app.routers import training as router_training

ROUTERS = [router_access, router_plant, router_inspection, router_panel_clean, router_inverter, router_power_data, router_fault, router_spare_part, router_transformer, router_switchgear, router_meter, router_weather, router_grid_connect, router_cable, router_security, router_maintenance, router_dc_box, router_energy_saving, router_training]
