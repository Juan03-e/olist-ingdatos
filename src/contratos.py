import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, Check, DataFrameSchema

ESTADOS_PEDIDO = ["created", "approved", "invoiced", "processing", "shipped",
                  "delivered", "canceled", "unavailable"]
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB",
       "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
LAT_BRASIL = (-33.75, 5.30)
LNG_BRASIL = (-73.99, -34.79)
FECHA_MIN = pd.Timestamp("2016-01-01")
FECHA_MAX = pd.Timestamp("2018-12-31")

fecha = lambda nulos: Column("datetime64[ns]", Check.in_range(FECHA_MIN, FECHA_MAX), nullable=nulos)
marca = Column(bool)


def orden_si_existen(antes, despues, excepto=None):
    def check(df):
        ok = df[antes].isna() | df[despues].isna() | (df[antes] <= df[despues])
        if excepto:
            ok = ok | df[excepto]
        return ok
    return Check(check, element_wise=False, error=f"{antes} <= {despues}")


schema_pedidos = DataFrameSchema(
    {
        "order_id": Column(str, unique=True),
        "customer_id": Column(str, unique=True),
        "customer_unique_id": Column(str),
        "customer_state": Column(str, Check.isin(UFS)),
        "customer_zip_code_prefix": Column(str, Check.str_matches(r"^\d{5}$")),
        "cliente_lat": Column(float, Check.in_range(*LAT_BRASIL), nullable=True),
        "cliente_lng": Column(float, Check.in_range(*LNG_BRASIL), nullable=True),
        "order_status": Column(str, Check.isin(ESTADOS_PEDIDO)),
        "order_purchase_timestamp": fecha(False),
        "order_approved_at": fecha(True),
        "order_delivered_carrier_date": fecha(True),
        "order_delivered_customer_date": fecha(True),
        "order_estimated_delivery_date": fecha(False),
        "n_items": Column(int, Check.ge(0)),
        "total_precio": Column(float, Check.ge(0)),
        "total_flete": Column(float, Check.ge(0)),
        "n_vendedores": Column(int, Check.ge(0)),
        "n_pagos": Column(int, Check.ge(0)),
        "total_pagado": Column(float, Check.ge(0)),
        "max_cuotas": Column(float, Check.ge(1), nullable=True),
        "n_resenas": Column(int, Check.in_range(0, 3)),
        "review_score": Column(float, Check.isin([1, 2, 3, 4, 5]), nullable=True),
        "dias_vs_estimado": Column(float, Check.in_range(-200, 200), nullable=True),
        "llego_tarde": Column("boolean", nullable=True),
        "sin_items": marca, "sin_pago": marca, "sin_resena": marca, "varias_resenas": marca,
        "resenas_distintas": marca, "transportista_despues_cliente": marca,
        "delivered_sin_fecha": marca, "no_entregado_con_fecha": marca,
        "delivered_sin_aprobacion": marca, "pago_distinto_items": marca,
        "cliente_sin_coordenadas": marca, "en_periodo_mensual": marca,
    },
    checks=[
        orden_si_existen("order_purchase_timestamp", "order_approved_at"),
        orden_si_existen("order_delivered_carrier_date", "order_delivered_customer_date",
                         excepto="transportista_despues_cliente"),
        Check(lambda df: ~((df["order_status"] == "delivered") & df["order_delivered_customer_date"].isna())
              | df["delivered_sin_fecha"], element_wise=False, error="delivered sin fecha no marcado"),
        Check(lambda df: (df["n_items"] == 0) == df["sin_items"], element_wise=False,
              error="sin_items coherente con n_items"),
        Check(lambda df: df["review_score"].isna() == df["sin_resena"], element_wise=False,
              error="sin_resena coherente con review_score"),
        Check(lambda df: df["llego_tarde"].isna() | (df["order_status"] == "delivered"), element_wise=False,
              error="llego_tarde solo en delivered"),
    ],
    strict=True,
    coerce=False,
)

schema_items = DataFrameSchema(
    {
        "order_id": Column(str),
        "order_item_id": Column(int, Check.ge(1)),
        "product_id": Column(str),
        "seller_id": Column(str),
        "shipping_limit_date": fecha(True),
        "price": Column(float, Check.gt(0)),
        "freight_value": Column(float, Check.ge(0)),
        "categoria": Column(str),
        "product_weight_g": Column(float, Check.gt(0), nullable=True),
        "seller_state": Column(str, Check.isin(UFS)),
        "seller_zip_code_prefix": Column(str, Check.str_matches(r"^\d{5}$")),
        "vendedor_lat": Column(float, Check.in_range(*LAT_BRASIL), nullable=True),
        "vendedor_lng": Column(float, Check.in_range(*LNG_BRASIL), nullable=True),
        "limite_envio_invalido": marca, "peso_invalido": marca, "sin_categoria": marca,
        "vendedor_sin_coordenadas": marca,
    },
    unique=["order_id", "order_item_id"],
    checks=[
        Check(lambda df: (df["categoria"] == "sin_categoria") == df["sin_categoria"], element_wise=False,
              error="sin_categoria coherente con categoria"),
        Check(lambda df: df["shipping_limit_date"].isna() == df["limite_envio_invalido"], element_wise=False,
              error="limite_envio_invalido coherente con shipping_limit_date"),
    ],
    strict=True,
)


def controlar_integridad(pedidos, items, n_orders=None):
    fallas = {}
    huerfanos = ~items["order_id"].isin(pedidos["order_id"])
    if huerfanos.any():
        fallas["items con order_id que no está en pedidos"] = int(huerfanos.sum())
    conteo = items.groupby("order_id").size().reindex(pedidos["order_id"], fill_value=0).to_numpy()
    distinto = conteo != pedidos["n_items"].to_numpy()
    if distinto.any():
        fallas["n_items no coincide con los ítems"] = int(distinto.sum())
    if n_orders is not None and len(pedidos) != n_orders:
        fallas["cantidad de pedidos distinta de orders"] = abs(len(pedidos) - n_orders)
    return fallas


def validar(pedidos, items, n_orders=None):
    resultado = []
    for nombre, schema, df in [("pedidos", schema_pedidos, pedidos), ("items", schema_items, items)]:
        try:
            schema.validate(df, lazy=True)
        except pa.errors.SchemaErrors as e:
            casos = e.failure_cases
            for (col, check), grupo in casos.groupby(["column", "check"], dropna=False):
                resultado.append({"tabla": nombre, "columna": col, "control": str(check), "casos": len(grupo)})
    for control, casos in controlar_integridad(pedidos, items, n_orders).items():
        resultado.append({"tabla": "pedidos/items", "columna": None, "control": control, "casos": casos})
    return pd.DataFrame(resultado, columns=["tabla", "columna", "control", "casos"])


def exigir(pedidos, items, n_orders=None):
    fallas = validar(pedidos, items, n_orders)
    if len(fallas):
        raise ValueError("El dataset curado no cumple el contrato:\n" + fallas.to_string(index=False))
    print("Contrato OK:", len(pedidos), "pedidos y", len(items), "ítems")


DISTANCIA_MAX_KM = 4500
MAX_UF_DISTINTA_PCT = 0.1
MAX_SIN_MUNICIPIO_PCT = 0.1

schema_features = DataFrameSchema(
    {
        "ratio_flete_precio": Column(float, Check.in_range(0, 25), nullable=True),
        "precio_medio_item": Column(float, Check.gt(0), nullable=True, required=False),
        "dias_prometidos": Column(float, Check.in_range(0, 180)),
        "horas_aprobacion": Column(float, Check.ge(0), nullable=True),
        "dia_semana": Column(int, Check.in_range(0, 6), required=False),
        "hora_compra": Column(int, Check.in_range(0, 23), required=False),
        "dias_a_black_friday": Column(int, Check.in_range(0, 183)),
        "compras_previas": Column(int, Check.ge(0), required=False),
        "peso_total_kg": Column(float, Check.gt(0), nullable=True),
        "indice_envio_dificil": Column(float, Check.in_range(0, 1), nullable=True),
        "tamano_pedido": Column("category", nullable=True),
        "mismo_estado": Column("boolean", nullable=True),
    },
    checks=[
        Check(lambda df: df["ratio_flete_precio"].isna() == (df["n_items"] == 0), element_wise=False,
              error="ratio_flete_precio nulo solo en pedidos sin ítems"),
    ],
    strict=False,
)

schema_espacial = DataFrameSchema(
    {
        "cod_municipio": Column(str, Check.str_matches(r"^\d{7}$"), nullable=True),
        "uf_municipio": Column(str, Check.isin(UFS), nullable=True),
        "distancia_vendedor_km": Column(float, Check.in_range(0, DISTANCIA_MAX_KM), nullable=True),
        "distancia_capital_km": Column(float, Check.in_range(0, 2000), nullable=True),
        "densidad_clientes_km2": Column(float, Check.gt(0), nullable=True),
        "es_capital": Column("boolean", nullable=True),
    },
    checks=[
        Check(lambda df: df["cod_municipio"].isna() == df["cliente_sin_coordenadas"], element_wise=False,
              error="todo pedido con coordenadas recibe un municipio"),
        Check(lambda df: df["uf_distinta"] == (df["uf_municipio"].notna() & (df["uf_municipio"] != df["customer_state"])),
              element_wise=False, error="uf_distinta coherente con el spatial join"),
        Check(lambda df: df["uf_distinta"].mean() * 100 <= MAX_UF_DISTINTA_PCT, element_wise=False,
              error=f"pedidos con municipio de otra UF <= {MAX_UF_DISTINTA_PCT}%"),
        Check(lambda df: df["municipio_por_cercania"].mean() * 100 <= MAX_SIN_MUNICIPIO_PCT, element_wise=False,
              error=f"pedidos asignados por cercanía <= {MAX_SIN_MUNICIPIO_PCT}%"),
        Check(lambda df: df["distancia_vendedor_km"].dropna().median() > 100, element_wise=False,
              error="mediana de distancia vendedor-cliente > 100 km (distancias en km, no en grados)"),
    ],
    strict=False,
)


def validar_enriquecido(gdf):
    resultado = []
    for nombre, schema in [("features", schema_features), ("espacial", schema_espacial)]:
        try:
            schema.validate(gdf, lazy=True)
        except pa.errors.SchemaErrors as e:
            for (col, check), grupo in e.failure_cases.groupby(["column", "check"], dropna=False):
                resultado.append({"contrato": nombre, "columna": col, "control": str(check), "casos": len(grupo)})
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        resultado.append({"contrato": "espacial", "columna": "geometry", "control": "CRS EPSG:4326", "casos": 1})
    fuera = gdf.geometry.notna() & ~gdf.geometry.is_empty & ~(
        gdf.geometry.y.between(*LAT_BRASIL) & gdf.geometry.x.between(*LNG_BRASIL))
    if fuera.any():
        resultado.append({"contrato": "espacial", "columna": "geometry", "control": "punto dentro de Brasil", "casos": int(fuera.sum())})
    return pd.DataFrame(resultado, columns=["contrato", "columna", "control", "casos"])


def exigir_enriquecido(gdf):
    fallas = validar_enriquecido(gdf)
    if len(fallas):
        raise ValueError("El dataset enriquecido no cumple el contrato:\n" + fallas.to_string(index=False))
    print("Contrato del enriquecido OK:", len(gdf), "pedidos")
