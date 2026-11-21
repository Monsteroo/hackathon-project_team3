# Приклади відповідей API (2026-11-21)

Скорочені реальні відповіді. Довгі поля обрізано (`…`), решта як прийшла.

## Zakaz: магазин (`GET /stores/`)

Елемент списку.

```json
{
  "id": "482010105",
  "name": "NOVUS SkyMall DRIVE",
  "retail_chain": "novus",
  "region_id": "kiev",
  "city": "kiev",
  "address": {
    "city": "Київ",
    "street": "Романа Шухевича",
    "building": "2т",
    "coords": {
      "lat": 50.4931815,
      "lng": 30.5581461
    }
  },
  "delivery_types": [
    "pickup",
    "plan"
  ],
  "opening_hours": {
    "from": "10:00",
    "to": "20:00"
  },
  "is_active": true
}
```
## Zakaz: товар (`GET /stores/{id}/products/search/`)

Елемент `results`. `price` у копійках, `weight` у грамах.

```json
{
  "ean": "04820222760249",
  "eans": [
    "04820222760249"
  ],
  "sku": "354304",
  "title": "Молоко Галичина ультрапастеризоване 2,5% 950г",
  "price": 7499,
  "price_wholesale": [
    {
      "min_qty": 2,
      "price": 7124,
      "due_date": null
    },
    {
      "min_qty": 12,
      "price": 6974,
      "due_date": null
    }
  ],
  "discount": {
    "status": false,
    "value": 0,
    "old_price": 7499,
    "due_date": null,
    "display_value": false
  },
  "bundle": 1,
  "unit": "pcs",
  "volume": null,
  "quantity": {
    "min": 1,
    "step": 1,
    "is_strict": false
  },
  "currency": "uah",
  "category_id": "uht-milk",
  "parent_category_id": "dairy-and-eggs",
  "category_filters": [],
  "description": "Молоко ультрапастеризоване 2,5% ТМ «Галичина» добре доповнить будь-яку страву аб…",
  "nutrition_facts": {
    "ingredient_energy": "53.00ккал",
    "ingredient_protein": "2.80г",
    "ingredient_fat": "2.50г",
    "ingredient_fats_saturated": "1.60г",
    "ingredient_carbohydrates": "4.70г",
    "ingredient_sugars": "4.70г",
    "ingredient_salt": "0.10г"
  },
  "slug": "moloko-galichina-950ml-ukrayina",
  "in_stock": true,
  "is_hit": false,
  "is_alcohol": false,
  "is_nicotine": false,
  "is_ready_meal": false,
  "is_new_product": false,
  "horeca_only": false,
  "excisable": false,
  "web_url": "https://novus.zakaz.ua/uk/products/moloko-galichina-950ml-ukrayina--04820222760249/",
  "ingredients": [
    "Молоко коров'яче незбиране, молоко коров'яче знежирене.<br>"
  ],
  "fat": "2.5%",
  "shelf_life": "90 діб",
  "temperature_range": "1...25",
  "pack_amount": null,
  "country": "Україна",
  "producer": {
    "trademark": "Галичина",
    "trademark_slug": "galichina",
    "website": "galychyna.com.ua",
    "name": "тов \"молочна компанія \"галичина\""
  },
  "img": {
    "s150x150": "https://img3.zakaz.ua/aa004a7689c241db9af22e36614f07f1/1759332972-s150x150.jpg",
    "s350x350": "https://img3.zakaz.ua/aa004a7689c241db9af22e36614f07f1/1759332972-s350x350.jpg"
  },
  "gallery": [
    {
      "s150x150": "https://img3.zakaz.ua/aa004a7689c241db9af22e36614f07f1/1759332972-s150x150.jpg",
      "s200x200": "https://img3.zakaz.ua/aa004a7689c241db9af22e36614f07f1/1759332972-s200x200.jpg",
      "s350x350": "https://img3.zakaz.ua/aa004a7689c241db9af22e36614f07f1/1759332972-s350x350.jpg",
      "s1350x1350": "https://img2.zakaz.ua/aa004a7689c241db9af22e36614f07f1/1759332972-s1350x1350.jpg"
    },
    {
      "s150x150": "https://img3.zakaz.ua/7954255a144f4b9fa0cc0391a182da08/1759332972-s150x150.jpg",
      "s200x200": "https://img2.zakaz.ua/7954255a144f4b9fa0cc0391a182da08/1759332972-s200x200.jpg",
      "s350x350": "https://img3.zakaz.ua/7954255a144f4b9fa0cc0391a182da08/1759332972-s350x350.jpg",
      "s1350x1350": "https://img2.zakaz.ua/7954255a144f4b9fa0cc0391a182da08/1759332972-s1350x1350.jpg"
    }
  ],
  "is_uber_item": false,
  "verbose_stock": "low_stock",
  "take_more": true,
  "is_own_brand": false,
  "available_for_cart": true,
  "own_brand_data": {},
  "taxons": [],
  "weight": 950.0,
  "has_similar_products": null,
  "hits": 2,
  "shopping_list_count": null
}
```
## Сільпо: магазин (`GET /branches`)

Елемент `items`. Координати — рядки.

```json
{
  "branchId": "1ed43e73-051b-6842-a111-a5ad042eb496",
  "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
  "externalId": "1998",
  "hasPickup": true,
  "latitude": "50.5202200000000000",
  "longitude": "30.5145200000000000",
  "cityFull": "Київ",
  "addressFull": "просп. Володимира Івасюка, 46",
  "distance": null,
  "open": true,
  "schedules": [
    {
      "branchId": "1ede5d03-56c2-6c14-8cc7-d9d98295aeba",
      "coreId": "1ed43e73-051b-6842-a111-a5ad042eb496",
      "dayOfTheWeek": 5,
      "openingHour": 5,
      "closingHour": 0,
      "openingMinute": 0,
      "closingMinute": 0
    },
    "… ще 6 днів"
  ]
}
```
## Сільпо: товар у списку (`GET /branches/{branchId}/products`)

Ціна в гривнях, вага лише в `displayRatio`, EAN немає.

```json
{
  "id": "1ed0767b-5557-61bc-82ae-eb0bb71c4ffc",
  "title": "Сир кисломолочний Яготинський 5%",
  "icon": "95fbf05c-c226-491d-b9a2-3b391fc54dbc.png",
  "price": 114,
  "oldPrice": null,
  "offerId": "1edfe25e-60c4-6988-8a31-ff832aac5e53",
  "ratio": "шт",
  "sectionSlug": "syr-kyslomolochnyi-4988",
  "companyId": "1ec88c5d-a050-669c-8467-570a157f3e31",
  "branchId": "00000000-0000-0000-0000-000000000000",
  "deliveryType": "DeliveryHome",
  "externalProductId": 802382,
  "promotions": [
    {
      "id": "national-cashback",
      "iconPath": "https://content.silpo.ua/ecom/productblock/26077.svg",
      "type": "set",
      "classActivity": null
    }
  ],
  "specialPrices": [],
  "createdAt": "2023-05-29T13:37:04+00:00",
  "slug": "syr-kyslomolochnyi-yagotynskyi-5-802382",
  "addToBasketStep": 1,
  "stock": 22,
  "displayPrice": 114,
  "displayOldPrice": null,
  "displayRatio": "350г",
  "guestProductRating": 4.2,
  "guestProductRatingCount": 143,
  "classifierSapId": "1edc408b-5ca5-6960-82c8-377f4c169cfc",
  "originType": null,
  "brandId": "1edc402d-aa55-68ee-a937-377f4c169cfc",
  "brandTitle": "Яготинське",
  "weighted": false,
  "blurForUnderAged": false,
  "modifier": null,
  "promos": [],
  "untappdRating": null,
  "vivinoRating": null,
  "isTobacco": false
}
```
## Сільпо: картка (`GET /branches/{branchId}/products/{slug}`)

Тут є `barcodes`. Блоки `ingredients`/`composition` порожні — типова ситуація.

```json
{
  "id": "1ed0767b-5557-61bc-82ae-eb0bb71c4ffc",
  "title": "Сир кисломолочний Яготинський 5%",
  "displayPrice": 114,
  "displayRatio": "350г",
  "barcodes": [
    "4823005207719",
    "0250014097576",
    "4823005207795"
  ],
  "media": [
    "95fbf05c-c226-491d-b9a2-3b391fc54dbc.png",
    "3447fd8c-4dde-4041-bb54-84987662ac14.jpg",
    "420560a8-8c71-44bd-9467-0d19b64c1512.jpg"
  ],
  "attributeGroups": [
    {
      "tag": "Опис",
      "key": "description",
      "attributes": []
    },
    {
      "tag": "Інгредієнти",
      "key": "ingredients",
      "attributes": []
    },
    {
      "tag": "Склад",
      "key": "composition",
      "attributes": []
    },
    {
      "tag": "Загальна інформація",
      "key": "generalInfo",
      "attributes": [
        {
          "attribute": {
            "key": "country",
            "id": "country",
            "title": "Країна"
          },
          "value": {
            "key": "1eef1f4c-5f89-6db8-9b53-2b6d83ba3109",
            "title": "Україна"
          }
        },
        {
          "attribute": {
            "key": "brand",
            "id": "brand",
            "title": "Торгова марка"
          },
          "value": {
            "key": "1edc402d-aa55-68ee-a937-377f4c169cfc",
            "title": "Яготинське"
          }
        },
        {
          "attribute": {
            "key": "__companyname",
            "id": "__companyname",
            "title": "Продавець"
          },
          "value": {
            "key": "ТОВ «СІЛЬПО-ФУД»",
            "title": "ТОВ «СІЛЬПО-ФУД»"
          }
        },
        "… ще 1"
      ]
    },
    {
      "tag": "Харчова цінність на 100 г",
      "key": "nutrient",
      "attributes": [
        {
          "attribute": {
            "key": "calorie",
            "id": "calorie",
            "title": "Енергетична цінність (кКал/кДЖ)"
          },
          "value": {
            "key": "117/491",
            "title": "117/491"
          }
        },
        {
          "attribute": {
            "key": "proteins",
            "id": "proteins",
            "title": "Білки (г)"
          },
          "value": {
            "key": null,
            "title": 16.2
          }
        },
        {
          "attribute": {
            "key": "fats",
            "id": "fats",
            "title": "Жири (г)"
          },
          "value": {
            "key": null,
            "title": 5
          }
        },
        "… ще 1"
      ]
    }
  ]
}
```
