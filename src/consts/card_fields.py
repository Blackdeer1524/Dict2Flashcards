from .. import StrEnum
from typing import TypedDict, NotRequired, Union


TagsScheme = dict[str, Union[str, list[str], "TagsScheme"]]

class CardFormat(TypedDict):
    word:        str        
    special:     NotRequired[list[str]]     
    definition:  NotRequired[str]  
    examples:    NotRequired[list[str]]    
    image_links: NotRequired[list[str]] 
    audio_links: NotRequired[list[str]] 
    tags:        NotRequired[TagsScheme]       


class CardFields(StrEnum):
    word        = "word"
    special     = "special"
    definition  = "definition"
    sentences   = "examples"
    img_links   = "image_links"
    audio_links = "audio_links"
    dict_tags   = "tags"