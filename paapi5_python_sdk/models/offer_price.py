# coding: utf-8

"""
  Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License").
  You may not use this file except in compliance with the License.
  A copy of the License is located at

      http://www.apache.org/licenses/LICENSE-2.0

  or in the "license" file accompanying this file. This file is distributed
  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
  express or implied. See the License for the specific language governing
  permissions and limitations under the License.
"""


"""
    ProductAdvertisingAPI

    https://webservices.amazon.com/paapi5/documentation/index.html  # noqa: E501
"""


import pprint
import re  # noqa: F401

import six

from paapi5_python_sdk.models.offer_savings import OfferSavings  # noqa: F401,E501
from paapi5_python_sdk.models.price_type import PriceType  # noqa: F401,E501


class OfferPrice(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """

    """
    Attributes:
      swagger_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    swagger_types = {
        'amount': 'float',
        'currency': 'str',
        'display_amount': 'str',
        'price_per_unit': 'float',
        'price_type': 'PriceType',
        'price_type_label': 'str',
        'savings': 'OfferSavings'
    }

    attribute_map = {
        'amount': 'Amount',
        'currency': 'Currency',
        'display_amount': 'DisplayAmount',
        'price_per_unit': 'PricePerUnit',
        'price_type': 'PriceType',
        'price_type_label': 'PriceTypeLabel',
        'savings': 'Savings'
    }

    def __init__(self, amount=None, currency=None, display_amount=None, price_per_unit=None, price_type=None, price_type_label=None, savings=None):  # noqa: E501
        """OfferPrice - a model defined in Swagger"""  # noqa: E501

        self._amount = None
        self._currency = None
        self._display_amount = None
        self._price_per_unit = None
        self._price_type = None
        self._price_type_label = None
        self._savings = None
        self.discriminator = None

        if amount is not None:
            self.amount = amount
        if currency is not None:
            self.currency = currency
        if display_amount is not None:
            self.display_amount = display_amount
        if price_per_unit is not None:
            self.price_per_unit = price_per_unit
        if price_type is not None:
            self.price_type = price_type
        if price_type_label is not None:
            self.price_type_label = price_type_label
        if savings is not None:
            self.savings = savings

    @property
    def amount(self):
        """Gets the amount of this OfferPrice.  # noqa: E501


        :return: The amount of this OfferPrice.  # noqa: E501
        :rtype: float
        """
        return self._amount

    @amount.setter
    def amount(self, amount):
        """Sets the amount of this OfferPrice.


        :param amount: The amount of this OfferPrice.  # noqa: E501
        :type: float
        """

        self._amount = amount

    @property
    def currency(self):
        """Gets the currency of this OfferPrice.  # noqa: E501


        :return: The currency of this OfferPrice.  # noqa: E501
        :rtype: str
        """
        return self._currency

    @currency.setter
    def currency(self, currency):
        """Sets the currency of this OfferPrice.


        :param currency: The currency of this OfferPrice.  # noqa: E501
        :type: str
        """

        self._currency = currency

    @property
    def display_amount(self):
        """Gets the display_amount of this OfferPrice.  # noqa: E501


        :return: The display_amount of this OfferPrice.  # noqa: E501
        :rtype: str
        """
        return self._display_amount

    @display_amount.setter
    def display_amount(self, display_amount):
        """Sets the display_amount of this OfferPrice.


        :param display_amount: The display_amount of this OfferPrice.  # noqa: E501
        :type: str
        """

        self._display_amount = display_amount

    @property
    def price_per_unit(self):
        """Gets the price_per_unit of this OfferPrice.  # noqa: E501


        :return: The price_per_unit of this OfferPrice.  # noqa: E501
        :rtype: float
        """
        return self._price_per_unit

    @price_per_unit.setter
    def price_per_unit(self, price_per_unit):
        """Sets the price_per_unit of this OfferPrice.


        :param price_per_unit: The price_per_unit of this OfferPrice.  # noqa: E501
        :type: float
        """

        self._price_per_unit = price_per_unit

    @property
    def price_type(self):
        """Gets the price_type of this OfferPrice.  # noqa: E501


        :return: The price_type of this OfferPrice.  # noqa: E501
        :rtype: PriceType
        """
        return self._price_type

    @price_type.setter
    def price_type(self, price_type):
        """Sets the price_type of this OfferPrice.


        :param price_type: The price_type of this OfferPrice.  # noqa: E501
        :type: PriceType
        """

        self._price_type = price_type

    @property
    def price_type_label(self):
        """Gets the price_type_label of this OfferPrice.  # noqa: E501


        :return: The price_type_label of this OfferPrice.  # noqa: E501
        :rtype: str
        """
        return self._price_type_label

    @price_type_label.setter
    def price_type_label(self, price_type_label):
        """Sets the price_type_label of this OfferPrice.


        :param price_type_label: The price_type_label of this OfferPrice.  # noqa: E501
        :type: str
        """

        self._price_type_label = price_type_label

    @property
    def savings(self):
        """Gets the savings of this OfferPrice.  # noqa: E501


        :return: The savings of this OfferPrice.  # noqa: E501
        :rtype: OfferSavings
        """
        return self._savings

    @savings.setter
    def savings(self, savings):
        """Sets the savings of this OfferPrice.


        :param savings: The savings of this OfferPrice.  # noqa: E501
        :type: OfferSavings
        """

        self._savings = savings

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value
        if issubclass(OfferPrice, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, OfferPrice):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
