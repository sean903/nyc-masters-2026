from ._anvil_designer import ItemTemplate1Template
from anvil import *


class ItemTemplate1(ItemTemplate1Template):
  def __init__(self, **properties):
    self.init_components(**properties)

    self.person_label.text = self.item["person"]
    self.avg_score_label.text = round(self.item["avg_score"], 2)

    self.player_1_header.text = self.item["player_1"]
    self.player_2_header.text = self.item["player_2"]
    self.player_3_header.text = self.item["player_3"]
    self.player_4_header.text = self.item["player_4"]
    self.player_5_header.text = self.item["player_5"]
    self.player_6_header.text = self.item["player_6"]

    self.score_1_label.text = self.format_score(self.item["score_1"])
    self.score_2_label.text = self.format_score(self.item["score_2"])
    self.score_3_label.text = self.format_score(self.item["score_3"])
    self.score_4_label.text = self.format_score(self.item["score_4"])
    self.score_5_label.text = self.format_score(self.item["score_5"])
    self.score_6_label.text = self.format_score(self.item["score_6"])

  def format_score(self, value):
    if value is None:
      return ""
    if value == 999 or value == 999.0:
      return "N/A"
    if float(value).is_integer():
      return str(int(value))
    return str(round(value, 1))