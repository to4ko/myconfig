class TilesCard extends HTMLElement {

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    this._DOMAIN_SCRIPT = ["script", "python_script"];
    this._DOMAIN_SENSOR = ["sensor", "binary_sensor", "device_tracker"];
    this._DOMAIN_NO_ONOFF = this._DOMAIN_SCRIPT.concat("sensor", "scene", "weblink");
    this._DOMAIN_INPUT_SELECT = ["input_select"];
    this._DOMAIN_REMOTE = ["remote"];
    this._ON_STATES = ["on", "open", "locked", "home"];
  }

  setConfig(config) {

    if(!config.entities) {
        throw new Error('Please define your entities');
    }

    const root = this.shadowRoot;
    if(root.lastChild) root.removeChild(root.lastChild);

    const cardConfig = Object.assign({}, config);

    const card = document.createElement('ha-card');
    card.header = cardConfig.card_settings.title;

    var cardStyle = document.createElement('style');
    cardStyle.id = "cardStyle";
    cardStyle.textContent += this._getDefaultTilesStyleValues(cardConfig);
    cardStyle.textContent += this._getCardStyle();
    cardStyle.textContent += this._getCardStylesValues(cardConfig.card_settings);
    root.appendChild(cardStyle);

    if(this._hasCardTheme(cardConfig)) {
      var themeStyle = document.createElement('style');
      themeStyle.id = "themeStyle";
      this.themeApplied = false;
      root.appendChild(themeStyle);
    }

    var entitiesStyleValues = document.createElement('style');
    entitiesStyleValues.id = "entitiesStyleValues";
    if(cardConfig.global_settings) entitiesStyleValues.textContent = this._getStylesPaperComponent(cardConfig.global_settings);
    card.appendChild(entitiesStyleValues);

    var content = this._createContentCard(cardConfig, entitiesStyleValues);

    card.appendChild(content);
    root.appendChild(card);
    this._config = cardConfig;
  }

  set hass(hass) {
    this.myHass = hass;
    var card = this.shadowRoot.lastChild;
    var entitiesTiles = this._config.entities;
    var cardConfig = this._config;

    if(this._hasCardTheme(cardConfig) && !this.themeApplied){
      this._setCardTheme(cardConfig.card_settings.theme, card);
      this.themeApplied = true;
    }

    this._updateContentCard(entitiesTiles, card);
 }

  _setCardTheme(themeName, card) {
    var theme = this.myHass.themes.themes[themeName];
    var style = document.createElement('style').style;
    for(var attribute in theme) {
      style.setProperty(`--${attribute}`, theme[attribute]);
    }
    card.parentNode.getElementById("themeStyle").textContent = `:host{${style.cssText}}\n`;
  }

  _hasCardTheme(cardConfig) {
    if(cardConfig.card_settings) {
      return cardConfig.card_settings.theme || (cardConfig.card_settings.templates && cardConfig.card_settings.templates.theme);
    }
    return '';
  }

  _createContentCard(config, entitiesStyleValues) {
    var entitiesTiles = config.entities;
    const content = document.createElement('div');
    content.className = "grid";
    content.id = "div-tiles";

    entitiesTiles.forEach((entity, index) => {

      var paperComponent;
      entity.id = "component_"+index;

      entity.domain = entity.entity ? entity.entity.split('.')[0] : "";
      entity.disable = (entity.disable === undefined) ? (config.global_settings && config.global_settings.disable) : entity.disable;

      if(this._DOMAIN_INPUT_SELECT.includes(entity.domain)) {
        
        entity.icon = (entity.icon === undefined) ? (config.global_settings && config.global_settings.icon) : entity.icon;

        if(!entity.icon) entity.icon = "";
        else if(typeof(entity.icon) == "string") entity.icon = {value: entity.icon};
        else if(typeof(entity.icon) == "object" && entity.icon.color && typeof(entity.icon.color) == "object") entity.icon.color = entity.icon.color.value;

        if(!entity.title && config.global_settings && config.global_settings.listbox && config.global_settings.listbox.title) 
          entity.title = config.global_settings.listbox.title;
          
        paperComponent = this._createPaperDropdownMenu(entity);
      } else {
        
        if(entity.label === undefined && config.global_settings && config.global_settings.label) {
          if(typeof(config.global_settings.label) == "string") entity.label = {value: config.global_settings.label};
          else entity.label = {value: config.global_settings.label.value};
        }

        if(entity.label_sec === undefined && config.global_settings && config.global_settings.label_sec) {
          if(typeof(config.global_settings.label_sec) == "string") entity.label_sec = {value: config.global_settings.label_sec};
          else entity.label_sec = {value: config.global_settings.label_sec.value};
        }

        if(entity.icon === undefined && config.global_settings && config.global_settings.icon) {
          if(typeof(config.global_settings.icon) == "string") entity.icon = {value: config.global_settings.icon};
          else {
            entity.icon = { value: config.global_settings.icon.value, 
                            value_on: config.global_settings.icon.value_on, 
                            value_off: config.global_settings.icon.value_off, 
                            value_disabled: config.global_settings.icon.value_disabled};
          } 
        }

        if(!entity.icon) entity.icon = "";
        else if(typeof(entity.icon) == "string") entity.icon = {value: entity.icon};
        if(!entity.label) entity.label = "";
        else if(typeof(entity.label) == "string") entity.label = {value: entity.label};
        if(!entity.label_sec) entity.label_sec = "";
        else if(typeof(entity.label_sec) == "string") entity.label_sec = {value: entity.label_sec};

        paperComponent = this._createPaperButton(entity);
      } 

      entitiesStyleValues.textContent += this._getStylesPaperComponent(entity);

      paperComponent.id = entity.id;
      content.appendChild(paperComponent);
    });

    return content;
  }

  _updateContentCard(entitiesTiles, card) {
    var cardConfig = this._config;
    var content = card.children.namedItem("div-tiles");
    var disableUnavailable = true

    if(cardConfig.global_settings && cardConfig.global_settings.disable_if_unavailable === false) disableUnavailable = false;

    // Compute card templates if exists
    if(cardConfig.card_settings.templates) this._computeCardStylesFromTemplate(card, cardConfig.card_settings);

    entitiesTiles.forEach((entity, index) => {

      var paperComponent = content.children["component_"+index]
      var ironIcon = paperComponent.getElementsByTagName('iron-icon').item(0);

      // Compute entity templates if exists
      this._addGlobalTemplates(cardConfig, entity);
      if(entity.templates) this._computeEntityStylesFromTemplate(paperComponent, entity);

      // Set component class
      paperComponent.className = this._getClassPaperButton(entity);
      entity.className = this._getClassPaperButton(entity);

      if(disableUnavailable && entity.className === 'unavailable') entity.unavailable = true;
      else entity.unavailable = false;

      // If disabled replace the classname
      if(entity.disable === true || entity.unavailable === true) {
        entity.oldIcon = this._getIconValue(entity);
        paperComponent.className = "disabled";
        entity.className = "disabled";
        paperComponent.disable(true);
      } else paperComponent.disable(false);

      if(ironIcon) {
        var icon = this._getIconValue(entity);
        ironIcon.removeAttribute("icon");
        ironIcon.removeAttribute("src");
        ironIcon.setAttribute((icon.indexOf("mdi:") >= 0) ? "icon" : "src", icon);
      }
      
      if(this._DOMAIN_INPUT_SELECT.includes(entity.domain)) {
        this._updatePaperDropdownMenu(paperComponent, entity);
      } else {
        var label = this._hasLabel(entity) ? this._getLabel(entity) : "";
        var labelSec = this._hasLabelSec(entity) ? this._getLabelSec(entity) : "";

        if(label) paperComponent.getElementsByClassName('label')[0].innerHTML = label;
        if(labelSec) paperComponent.getElementsByClassName('labelSec')[0].innerHTML = labelSec;
      }

    });
  }

  _createPaperButton(entity) {
    var paperButton = document.createElement('paper-button');
    paperButton.raised = true;
    paperButton.animate = true;
    paperButton.tabIndex = 0;

    if(this._hasLabel(entity)){
      var div = document.createElement('div');
      div.className = "label";
      div.innerHTML = entity.label.value;
      paperButton.appendChild(div);
    }

    if(this._hasIcon(entity)){
      var div = document.createElement('div');
      div.className = "icon";
      var ironIcon = document.createElement('iron-icon');
      div.appendChild(ironIcon);
      paperButton.appendChild(div);
    }

    if(this._hasLabelSec(entity)){
      var div = document.createElement('div');
      div.className = "labelSec";
      div.innerHTML = entity.label_sec.value;
      paperButton.appendChild(div);
    }

    paperButton.disable = function(value){
      paperButton.disabled = (value === true) ? true : false;
    };

    if(this._isClickable(entity)) paperButton.addEventListener('click', event => { this._onClick(entity) });
    else paperButton.style.setProperty("cursor", "default");

    return paperButton;
  }

  _isClickable(entity){
    return entity.domain || entity.more_info || entity.service;
  }

  _createPaperDropdownMenu(entity){
    var divPaperDropdownMenu = document.createElement('tiles-listbox');
    var paperDropdownMenu = document.createElement('paper-dropdown-menu');
    var paperListbox = document.createElement('paper-listbox');
    var optionsList;

    if(entity.icon && entity.icon.color) entity.icon.color = {value: entity.icon.color};
    
    paperDropdownMenu.label = entity.title ? entity.title : "";
    paperDropdownMenu.className = "dropdownMenu";
    paperDropdownMenu.styleApplied = false;
    paperDropdownMenu.appendChild(paperListbox);
    paperListbox.tabIndex = 0;
    paperListbox.slot = "dropdown-content";
    entity.service = "input_select.select_option";

    if(this._hasIcon(entity)){
      var div = document.createElement('div');
      div.className = "icon";
      var ironIcon = document.createElement('iron-icon');
      div.appendChild(ironIcon);
      divPaperDropdownMenu.appendChild(div);
    }

    divPaperDropdownMenu.loadItensList = function(card, optionsListTemp) {
      optionsList = optionsListTemp;
      if(paperListbox.childElementCount <= 0){
        optionsList.forEach(item => {
          var paperItem = document.createElement('paper-item');
          paperItem.innerHTML = item;
          paperItem.className = "itemLista";
          paperItem.style.setProperty("cursor", "pointer");
          paperItem.addEventListener('click', event => {
            entity.data = { entity_id: entity.entity, option: item };
            card._onClick(entity);
          });
          paperListbox.appendChild(paperItem);
        });
      }
    };

    divPaperDropdownMenu.disable = function(value){
      paperDropdownMenu.disabled = (value === true) ? true : false;
    };

    divPaperDropdownMenu.setItem = function(selectedItem){
      paperListbox.selected = optionsList.indexOf(selectedItem);
    };

    divPaperDropdownMenu.appendChild(paperDropdownMenu);

    return divPaperDropdownMenu;
  }

  _updatePaperDropdownMenu(divPaperDropdownMenu, entity){
    var paperDropdownMenu = divPaperDropdownMenu.getElementsByTagName('paper-dropdown-menu').item(0);
    var inputSelect = this.myHass.states[entity.entity];
    var optionsList = inputSelect.attributes.options;
    var selectedItem = inputSelect.state;

    divPaperDropdownMenu.loadItensList(this, optionsList);
    divPaperDropdownMenu.setItem(selectedItem);

    if(paperDropdownMenu.shadowRoot && !divPaperDropdownMenu.styleApplied) {
      var paperInputContainer = paperDropdownMenu.shadowRoot.children[2].children[0].children[1].shadowRoot.children[1];
      var divInputWrapper = paperInputContainer.shadowRoot.children[2];
      var paperInputLabel = paperInputContainer.children[1];
      paperInputContainer.setAttribute("style", "padding: 0px;");
      divInputWrapper.setAttribute("style", "height: var(--tiles-listbox-input-height, var(--tiles-default-listbox-input-height));");
      paperInputLabel.setAttribute("style", "height: var(--tiles-listbox-title-height, var(--tiles-default-listbox-title-height));");
      var input = paperInputContainer.children[2].children[0];
      input.setAttribute("style", `color: var(--tiles-listbox-input-color, var(--tiles-default-listbox-input-color)); 
                                   text-transform: var(--tiles-listbox-input-transform, var(--tiles-default-listbox-input-transform));`);
      if(!entity.title) paperInputContainer.shadowRoot.children[1].style.display = "none";

      divPaperDropdownMenu.styleApplied = true;
    }
  }

  _getCardStylesValues(config) {
    let style = '\n';
    style += ':host {\n';
    style += '/*CARD SETTINGS VALUES*/\n';
    if(config.title) style += ` --tiles-card-padding-top: 0px;\n`;
    if(config.title_color) style += ` --tiles-card-title-color: ${config.title_color};\n`;
    if(config.title_align) style += ` --tiles-card-title-align: ${config.title_align};\n`;
    if(config.gap) style += ` --tiles-card-gap: ${config.gap};\n`;
    if(config.padding) style += ` --tiles-card-padding: ${config.padding};\n`;
    if(config.background) style += ` --tiles-card-background: ${config.background};\n`;
    
    if(config.align) { 
      if(config.align == "left") style += ` --tiles-card-align: start;\n`;
      if(config.align == "center") style += ` --tiles-card-align: center;\n`;
      if(config.align == "right") style += ` --tiles-card-align: end;\n`;
    }

    if(config.display) {
      if(config.display == "none") style += ` --tiles-card-display: none;\n`;
      if(config.display == "hidden") style += ` --tiles-card-visibility: hidden;\n`;
    }

    if(config.columns) style += ` --tiles-card-columns: ${config.columns};\n`;
    if(config.column_width) style += ` --tiles-card-column-width: ${(config.column_width) == 'auto' ? '1fr' : config.column_width};\n`;
    if(config.row_height) style += ` --tiles-card-row-height: ${config.row_height};\n`;

    return style+"}\n";
  }

  _getDefaultTilesStyleValues(cardConfig){
    let style = '\n';
    style += ':host {\n';
    style += '/*DEFAULT CARD VALUES*/\n';
    style += ` --tiles-default-card-align: start;\n`;
    style += ` --tiles-default-card-grid-display: grid;\n`;
    style += ` --tiles-default-card-columns: 3;\n`;
    style += ` --tiles-default-card-column-width: 1fr;\n`;
    style += ` --tiles-default-card-row-height: 1fr;\n`;
    style += ` --tiles-default-card-gap: 5px;\n`;
    style += ` --tiles-default-card-padding: 16px;\n`;
    style += ` --tiles-default-card-display: block;\n`;
    style += ` --tiles-default-card-visibility: visible;\n`;
    style += ` --tiles-default-card-title-color: var(--primary-text-color);\n`;
    style += ` --tiles-default-card-title-align: left;\n`;
    style += ` --tiles-default-card-background: var(--tiles-default-card-title-align);\n`;
    style += ` --tiles-default-card-background-size: cover;\n`;
    style += ` --tiles-default-card-background-repeat: no-repeat;\n`;
    style += ` --tiles-default-border-size: 0px;\n`;
    style += ` --tiles-default-border-radius: 3px;\n`;
    style += ` --tiles-default-border-style: solid;\n`;
    style += ` --tiles-default-icon-size: 24px;\n`;
    style += ` --tiles-default-icon-padding: 5px;\n`;
    style += ` --tiles-default-labels-size: 1em;\n`;
    style += ` --tiles-default-labels-padding: 0px;\n`;
    style += ` --tiles-default-opacity: 1;\n`;
    style += ` --tiles-default-opacity-disabled: 0.5;\n`;
    style += ` --tiles-default-padding: 0px;\n`;
    style += ` --tiles-default-listbox-padding: 0px;\n`;
    style += ` --tiles-default-dropdownmenu-padding: 0px 5px;\n`;
    style += ` --tiles-default-grayscale: none;\n`;
    style += ` --tiles-default-contents-color: var(--primary-text-color);\n`;
    style += ` --tiles-default-box-shadow: none;\n`;
    style += ` --tiles-default-image-size: contain;\n`;
    style += ` --tiles-default-grid-area: auto / auto / span 1 / span 1;\n`;
    style += ` --tiles-default-display: flex;\n`;
    style += ` --tiles-default-visibility: visible;\n`;
    style += ` --tiles-default-background: var(--primary-color);\n`;
    style += ` --tiles-default-margin: 0;\n`;
    style += ` --tiles-default-min-width: 10px;\n`;
    style += ` --tiles-default-min-height: 10px;\n`;
    style += ` --tiles-default-listbox-orientation: row;\n`;
    style += ` --tiles-default-orientation: column;\n`;
    style += ` --tiles-default-vertical-align: center;\n`;
    style += ` --tiles-default-horizontal-align: center;\n`;
    style += ` --tiles-default-text-align: center;\n`;
    style += ` --tiles-default-background-disabled: var(--tiles-background,  var(--tiles-default-background));\n`;
    style += ` --tiles-default-border-color-disabled: var(--tiles-border-color, var(--tiles-default-contents-color));\n`;
    style += ` --tiles-default-grayscale-disabled: var(--tiles-grayscale, var(--tiles-default-grayscale));\n`;
    style += ` --tiles-default-dropdownmenu-width: 100%;\n`;
    style += ` --tiles-default-listbox-title-transform: none;\n`;
    style += ` --tiles-default-listbox-title-color: var(--tiles-default-contents-color);\n`;
    style += ` --tiles-default-listbox-background-list-color: var(--tiles-background, var(--primary-color));\n`;
    style += ` --tiles-default-listbox-itens-color: var(--tiles-listbox-input-color, var(--tiles-listbox-title-color, var(--tiles-default-contents-color)));\n`;
    style += ` --tiles-default-listbox-itens-size: var(--tiles-listbox-input-size, var(--paper-input-container-shared-input-style_-_font-size, var(--tiles-default-titles-size)));\n`;
    style += ` --tiles-default-listbox-itens-transform: var(--tiles-listbox-input-transform, var(--tiles-listbox-title-transform, none));\n`;
    style += ` --tiles-default-label-transform: uppercase;\n`;
    style += ` --tiles-default-listbox-input-height: none;\n`;
    style += ` --tiles-default-listbox-title-height: none;\n`;
    style += ` --tiles-default-listbox-input-color: var(--tiles-listbox-title-color, var(--tiles-default-contents-color));\n`; 
    style += ` --tiles-default-listbox-input-transform: var(--tiles-listbox-title-transform, none);\n`; 

    return style+"}\n";
  }

  _getStylesPaperComponent(tilesConfig) {
    let style = '';

    if(tilesConfig.id && (tilesConfig.column || tilesConfig.column_span || tilesConfig.row || tilesConfig.row_span)){
      const column = tilesConfig.column ? tilesConfig.column : 'auto';
      const column_span = tilesConfig.column_span ? tilesConfig.column_span : 1;
      const row = tilesConfig.row ? tilesConfig.row : 'auto';
      const row_span = tilesConfig.row_span ? tilesConfig.row_span : 1;

      style += ` --tiles-grid-area: ${row} / ${column} / span ${row_span} / span ${column_span};\n`;
    }

    if(tilesConfig.label && !this._DOMAIN_INPUT_SELECT.includes(tilesConfig.domain)) computeLabelStyle(tilesConfig, "label");
    if(tilesConfig.label_sec && !this._DOMAIN_INPUT_SELECT.includes(tilesConfig.domain)) computeLabelStyle(tilesConfig, "label_sec");

    if(tilesConfig.listbox || this._DOMAIN_INPUT_SELECT.includes(tilesConfig.domain)) {

      var listbox = tilesConfig.listbox ? tilesConfig.listbox : tilesConfig;

      if(listbox.title_color) style += ` --tiles-listbox-title-color: ${listbox.title_color};\n`; //for list label
      if(listbox.title_color) style += ` --paper-font-subhead_-_font-color: ${listbox.title_color};\n`; //for list label
      if(listbox.title_size) style += ` --paper-font-subhead_-_font-size: ${listbox.title_size};\n`; //for list label
      if(listbox.title_height) style += ` --tiles-listbox-title-height: ${listbox.title_height};\n`;
      if(listbox.title_transform) style += ` --tiles-listbox-title-transform: ${listbox.title_transform};\n`;

      if(listbox.input_color) style += ` --tiles-listbox-input-color: ${listbox.input_color};\n`; //for list label
      if(listbox.input_color) style += ` --paper-font-subhead_-_font-color: ${listbox.input_color};\n`; //for list label
      if(listbox.input_size) style += ` --paper-input-container-shared-input-style_-_font-size: ${listbox.input_size};\n`; //for list label
      if(listbox.input_height) style += ` --tiles-listbox-input-height: ${listbox.input_height};\n`;
      if(listbox.input_transform) style += ` --tiles-listbox-input-transform: ${listbox.input_transform};\n`;

      if(listbox.itens_color) style += ` --tiles-listbox-itens-color: ${listbox.itens_color};\n`; //for list label
      if(listbox.itens_color) style += ` --paper-font-subhead_-_font-color: ${listbox.itens_color};\n`; //for list label
      if(listbox.itens_size) style += ` --tiles-listbox-itens-size: ${listbox.itens_size};\n`; //for list label
      if(listbox.itens_transform) style += ` --tiles-listbox-itens-transform: ${listbox.itens_transform};\n`;
      if(listbox.list_background) style += ` --tiles-listbox-background-list-color: ${listbox.list_background};\n`;

      if(listbox.padding) style += ` --tiles-dropdownmenu-padding: ${listbox.padding};\n`;

    }

    function computeLabelStyle(config, labelName) {
      var styleLabel = labelName.replace(/_/g, "-");
      if(config[labelName].color) computeStatesAttributes(config, labelName, "color");
      if(config[labelName].size) style += ` --tiles-${styleLabel}-size: ${config[labelName].size};\n`;
      if(config[labelName].transform) style += ` --tiles-${styleLabel}-transform: ${config[labelName].transform};\n`;
      if(config[labelName].padding) style += ` --tiles-${styleLabel}-padding: ${config[labelName].padding};\n`;
      if(config[labelName].font) style += ` --tiles-${styleLabel}-font: ${config[labelName].font};\n`;
      if(config[labelName].decoration) style += ` --tiles-${styleLabel}-decoration: ${config[labelName].decoration};\n`;
    }

    if(tilesConfig.background) {
      computeStatesAttributes(tilesConfig, "background");
      if(tilesConfig.background.image_size) style += ` --tiles-image-size: ${tilesConfig.background.image_size};\n`;
    }

    if(tilesConfig.icon) {
      if(tilesConfig.icon.color) computeStatesAttributes(tilesConfig, "icon", "color");
      if(tilesConfig.icon.size) style += ` --tiles-icon-size: ${tilesConfig.icon.size};\n`;
      if(tilesConfig.icon.padding) style += ` --tiles-icon-padding: ${tilesConfig.icon.padding};\n`;
    }

    if(tilesConfig.border) {
      if(typeof(tilesConfig.border) == "string") tilesConfig.border = {size: tilesConfig.border};
      if(tilesConfig.border.color) computeStatesAttributes(tilesConfig, "border", "color");
      if(tilesConfig.border.size) style += ` --tiles-border-size: ${tilesConfig.border.size};\n`;
      if(tilesConfig.border.radius) style += ` --tiles-border-radius: ${tilesConfig.border.radius};\n`;
      if(tilesConfig.border.style) style += ` --tiles-border-style: ${tilesConfig.border.style};\n`;
    }

    if(tilesConfig.orientation) {
      if(tilesConfig.orientation == "horizontal") style += ` --tiles-orientation: row;\n`;
      if(tilesConfig.orientation == "vertical") style += ` --tiles-orientation: column;\n`; //default
    }

    function computeStatesAttributes(config, attributeName, subAttribute) {
      var styleLabel = attributeName.replace(/_/g, "-");
      var attribute = subAttribute ? config[attributeName][subAttribute] : config[attributeName];
      if(typeof(attribute) != "object") {
        attribute = {value: attribute};
        if(subAttribute) config[attributeName][subAttribute] = attribute;
        else config[attributeName] = attribute;
      } 
      subAttribute = subAttribute ? "-"+subAttribute : "";
      if(attribute.value != undefined) style += ` --tiles-${styleLabel+subAttribute}: ${attribute.value};\n`;
      if(attribute.value_on != undefined) style += ` --tiles-${styleLabel+subAttribute}-on: ${attribute.value_on};\n`;
      if(attribute.value_off != undefined) style += ` --tiles-${styleLabel+subAttribute}-off: ${attribute.value_off};\n`;
      if(attribute.value_disabled != undefined) style += ` --tiles-${styleLabel+subAttribute}-disabled: ${attribute.value_disabled};\n`;
    }

    if(tilesConfig.align) {
      if(tilesConfig.orientation == "horizontal") {
        if(tilesConfig.align.indexOf("left") >= 0) style += ` --tiles-horizontal-align: flex-start;\n`;
        if(tilesConfig.align.indexOf("right") >= 0) style += ` --tiles-horizontal-align: flex-end;\n`;
        if(tilesConfig.align.indexOf("top") >= 0) style += ` --tiles-vertical-align: flex-start;\n`;
        if(tilesConfig.align.indexOf("bottom") >= 0) style += ` --tiles-vertical-align: flex-end;\n`;
        if(tilesConfig.align.indexOf("middle") >= 0) style += ` --tiles-vertical-align: center;\n`;
        if(tilesConfig.align.indexOf("center") >= 0) style += ` --tiles-horizontal-align: center;\n`;
      } else {
        if(tilesConfig.align.indexOf("left") >= 0) style += ` --tiles-vertical-align: flex-start;\n`;
        if(tilesConfig.align.indexOf("right") >= 0) style += ` --tiles-vertical-align: flex-end;\n`;
        if(tilesConfig.align.indexOf("top") >= 0) style += ` --tiles-horizontal-align: flex-start;\n`;
        if(tilesConfig.align.indexOf("bottom") >= 0) style += ` --tiles-horizontal-align: flex-end;\n`;
        if(tilesConfig.align.indexOf("center") >= 0) style += ` --tiles-vertical-align: center;\n`;
        if(tilesConfig.align.indexOf("middle") >= 0) style += ` --tiles-horizontal-align: center;\n`;
      }

      if(tilesConfig.align.indexOf("left") >= 0) style += ` --tiles-text-align: left;\n`;
      if(tilesConfig.align.indexOf("right") >= 0) style += ` --tiles-text-align: right;\n`;
      if(tilesConfig.align.indexOf("center") >= 0) style += ` --tiles-text-align: center;\n`;
    }

    if(tilesConfig.display) {
      if(tilesConfig.display == "none") style += ` --tiles-display: none;\n`;
      if(tilesConfig.display == "hidden") style += ` --tiles-visibility: hidden;\n`;
    }
    
    if(tilesConfig.opacity != undefined) {
      computeStatesAttributes(tilesConfig, "opacity");
    }
    
    if(tilesConfig.grayscale != undefined) {
      computeStatesAttributes(tilesConfig, "grayscale");
    }
    
    if(tilesConfig.padding) style += ` --tiles-padding: ${tilesConfig.padding};\n`;
    
    if(tilesConfig.shadow) {
      var shadow = tilesConfig.shadow;
      if((tilesConfig.shadow.indexOf("elevation:") >= 0)) {
        shadow = shadow.split(":")[1];
        style += ` --tiles-box-shadow: var(--shadow-elevation-${shadow.trim()}_-_box-shadow);\n`;
      } else {
        style += ` --tiles-box-shadow: ${shadow};\n`;
      }
      
    } 

    if(style) style = (tilesConfig.id ? `\n#${tilesConfig.id} {\n` : '\n:host {\n/*COMMON SETTINGS VALUES*/\n')+style+"}\n";

    return style;
  }

  _addGlobalTemplates(cardConfig, entity){
    if(cardConfig.global_settings && cardConfig.global_settings.templates) {

      var globalTempalates = cardConfig.global_settings.templates;

      if(!entity.templates) entity.templates = {};

      if(!entity.templates.background) entity.templates.background = globalTempalates.background ? globalTempalates.background : "";
      if(!entity.templates.label_color) entity.templates.label_color = globalTempalates.label_color ? globalTempalates.label_color : "";
      if(!entity.templates.label_transform) entity.templates.label_transform = globalTempalates.label_transform ? globalTempalates.label_transform : "";
      if(!entity.templates.label_sec_color) entity.templates.label_sec_color = globalTempalates.label_sec_color ? globalTempalates.label_sec_color : "";
      if(!entity.templates.label_sec_transform) entity.templates.label_sec_transform = globalTempalates.label_sec_transform ? globalTempalates.label_sec_transform : "";
      if(!entity.templates.icon_color) entity.templates.icon_color = globalTempalates.icon_color ? globalTempalates.icon_color : "";
      if(!entity.templates.border_color) entity.templates.border_color = globalTempalates.border_color ? globalTempalates.border_color : "";
      if(!entity.templates.display) entity.templates.display = globalTempalates.display ? globalTempalates.display : "";
      if(!entity.templates.disable) entity.templates.disable = globalTempalates.disable ? globalTempalates.disable : "";
      if(!entity.templates.opacity) entity.templates.opacity = globalTempalates.opacity ? globalTempalates.opacity : "";
      if(!entity.templates.grayscale) entity.templates.grayscale = globalTempalates.grayscale ? globalTempalates.grayscale : "";

      if(!entity.templates.title_color) entity.templates.title_color = globalTempalates.title_color ? globalTempalates.title_color : "";
      if(!entity.templates.input_color) entity.templates.input_color = globalTempalates.input_color ? globalTempalates.input_color : "";
      if(!entity.templates.itens_color) entity.templates.itens_color = globalTempalates.itens_color ? globalTempalates.itens_color : "";

      if(!entity.templates.style) entity.templates.style = globalTempalates.style ? globalTempalates.style : "";

    }
  }

  _computeCardStylesFromTemplate(card, cardConfig){
    if(cardConfig.templates.display) {
      var display = this._getValueFromTemplate(cardConfig, "display");
      card.style.removeProperty("--tiles-card-display");
      card.style.removeProperty("--tiles-card-visibility");
      if(display == "none") card.style.setProperty("--tiles-card-display", "none");
      if(display == "hidden") card.style.setProperty("--tiles-card-visibility", "hidden");
    }
    if(cardConfig.templates.background) card.style.setProperty("--tiles-card-background", this._getValueFromTemplate(cardConfig, "background"));
    if(cardConfig.templates.theme) this._setCardTheme(this._getValueFromTemplate(cardConfig, "theme"), card);
    if(cardConfig.templates.style) card.style.cssText += this._getValueFromTemplate(cardConfig, "style");
  }

  _computeEntityStylesFromTemplate(paperComponent, entity){
    if(entity.templates.background) paperComponent.style.setProperty("--tiles-background", this._getValueFromTemplate(entity, "background"));
    if(entity.templates.background && entity.templates.background.indexOf("url(:") < 0) paperComponent.style.setProperty("--tiles-list-color", this._getValueFromTemplate(entity, "background"));
    if(entity.templates.label_color) paperComponent.style.setProperty("--tiles-label-color", this._getValueFromTemplate(entity, "label_color"));
    if(entity.templates.label_transform) paperComponent.style.setProperty("--tiles-label-transform", this._getValueFromTemplate(entity, "label_transform"));
    if(entity.templates.label_sec_color) paperComponent.style.setProperty("--tiles-label-sec-color", this._getValueFromTemplate(entity, "label_sec_color"));
    if(entity.templates.label_sec_transform) paperComponent.style.setProperty("--tiles-label-sec-transform", this._getValueFromTemplate(entity, "label_sec_transform"));
    if(entity.templates.icon_color) paperComponent.style.setProperty("--tiles-icon-color", this._getValueFromTemplate(entity, "icon_color"));
    if(entity.templates.border_color) paperComponent.style.setProperty("--tiles-border-color", this._getValueFromTemplate(entity, "border_color"));
    if(entity.templates.display) {
      var display = this._getValueFromTemplate(entity, "display");
      paperComponent.style.removeProperty("--tiles-visibility");
      paperComponent.style.removeProperty("--tiles-display");
      if(display == "none") paperComponent.style.setProperty("--tiles-display", "none");
      if(display == "hidden") paperComponent.style.setProperty("--tiles-visibility", "hidden");
    }
    if(entity.templates.disable) entity.disable = this._getValueFromTemplate(entity, "disable");
    if(entity.templates.opacity) paperComponent.style.setProperty("--tiles-opacity", this._getValueFromTemplate(entity, "opacity"));
    if(entity.templates.grayscale) paperComponent.style.setProperty("--tiles-grayscale", this._getValueFromTemplate(entity, "grayscale"));

    if(entity.templates.title_color) paperComponent.style.setProperty("--tiles-listbox-title-color", this._getValueFromTemplate(entity, "title_color"));
    if(entity.templates.input_color) paperComponent.style.setProperty("--tiles-listbox-input-color", this._getValueFromTemplate(entity, "input_color"));
    if(entity.templates.itens_color) paperComponent.style.setProperty("--tiles-listbox-itens-color", this._getValueFromTemplate(entity, "itens_color"));

    if(entity.templates.style) paperComponent.style.cssText += this._getValueFromTemplate(entity, "style");
  }

  _getValueFromTemplate(entity, template) {
    const state = this.myHass.states[entity.entity] && this.myHass.states[entity.entity].state || null;
    const attributes = this.myHass.states[entity.entity] && this.myHass.states[entity.entity].attributes || null;
    const entities = this.myHass.states;
    return Function('state', 'attributes', 'entities', entity.templates[template])(state, attributes, entities);
  }
  
  _hasLabel(entity) {
    return entity.label.value || entity.label.state || (entity.templates && entity.templates.label);
  }

  _hasLabelSec(entity) {
    return entity.label_sec.value || entity.label_sec.state || (entity.templates && entity.templates.label_sec);
  }

  _hasIcon(entity) {
    return entity.icon.value || entity.icon.value_on || entity.icon.value_off || (entity.templates && entity.templates.icon);
  }

  _getLabel(entity) {
    if(entity.label && entity.label.value) {
      return entity.label.value;
    } else if(entity.templates && entity.templates.label) {
      return this._getValueFromTemplate(entity, 'label');
    } else if(entity.label.state || this._DOMAIN_SENSOR.includes(entity.entity ? entity.entity.split('.')[0] : "")) {
      const stateObj = this.myHass.states[entity.label.state];
      if(stateObj) {
        return stateObj.attributes && stateObj.attributes.unit_of_measurement ? `${stateObj.state} ${stateObj.attributes.unit_of_measurement}` : stateObj.state;
      }
    }
    return '';
  }
  
  _getLabelSec(entity) {
    return this._getLabel({
      templates: {label: (entity.templates && entity.templates.label_sec) ? entity.templates.label_sec : null},
      label: {value: entity.label_sec.value, state: entity.label_sec.state},
      entity: entity.entity });
  }

  _getIconValue(entity) {
    var iconValue = entity.oldIcon;
    if(entity.icon && entity.icon.value) iconValue = entity.icon.value;
    if(entity.icon && entity.icon.value_on && entity.className == "on") iconValue = entity.icon.value_on;
    if(entity.icon && entity.icon.value_off && entity.className == "off") iconValue = entity.icon.value_off;
    if(entity.icon && entity.icon.value_disabled && entity.className == "disabled") iconValue = entity.icon.value_disabled;
    if(entity.templates && entity.templates.icon) iconValue = this._getValueFromTemplate(entity, "icon");

    return iconValue;
  }
  
  _getClassPaperButton(entity) {
    var entityId = entity.entity;
    if(entity.templates && entity.templates.class_name) {
      return this._getValueFromTemplate(entity, "class_name");
    } else if(!entityId || this._DOMAIN_NO_ONOFF.includes(entityId.split('.')[0])) {
      return '';
    } else if(!entityId || this._DOMAIN_INPUT_SELECT.includes(entityId.split('.')[0])) {
      return '';
    } else if(this.myHass.states[entityId] && this.myHass.states[entityId].state === 'unavailable') {
      return 'unavailable';
    } else {
      return this.myHass.states[entityId] && this._ON_STATES.includes(this.myHass.states[entityId].state) ? 'on' : 'off';
    }
  }

  _onClick(entity) {
    const entity_id = entity.entity;
    const stateDomain = entity_id ? entity_id.split('.')[0] : "";
    if(stateDomain === 'weblink') {
      window.open(this.myHass.states[entity_id].state, '_blank');
    } else if(this._DOMAIN_SENSOR.includes(stateDomain) || entity.more_info) {
      this._fire('hass-more-info', { entityId: entity.more_info || entity_id });
    } else {
      let serviceDomain, service;
      const data = entity.data || { entity_id: entity_id };
      if(entity.service) {
        serviceDomain = entity.service.split('.')[0];
        service = entity.service.split('.')[1];
      } else if(this._DOMAIN_REMOTE.includes(stateDomain)){
        serviceDomain = entity_id.split('.')[0];
        service = data.service || "send_command";
      } else if(this._DOMAIN_SCRIPT.includes(stateDomain)) {
        serviceDomain = stateDomain;
        service = entity_id.split('.')[1];
      } else {
        const isOn = this._ON_STATES.includes(this.myHass.states[entity_id].state);
        switch (stateDomain) {
          case 'lock':
            serviceDomain = 'lock';
            service = isOn ? 'unlock' : 'lock';
            break;
          case 'cover':
            serviceDomain = 'cover';
            service = isOn ? 'close' : 'open';
            break;
          case 'scene':
            serviceDomain = 'scene';
            service = 'turn_on';
            break;
          default:
            serviceDomain = 'homeassistant';
            service = isOn ? 'turn_off' : 'turn_on';
        }
      }
      this.myHass.callService(serviceDomain, service, data);
    }
  }

  _fire(type, detail, options) {
    options = options || {};
    detail = (detail === null || detail === undefined) ? {} : detail;
    const event = new Event(type, {
      bubbles: options.bubbles === undefined ? true : options.bubbles,
      cancelable: Boolean(options.cancelable),
      composed: options.composed === undefined ? true : options.composed
    });
    event.detail = detail;
    const node = options.node || this;
    node.dispatchEvent(event);
    return event;
  }

  getCardSize() {
    var size = (this._config.entities.length / this._config.card_settings.columns);
    if(this._config.card_settings.title) size++;
    return size;
  }

  _getCardStyle() {
    return `
      ha-card {
          display: var(--tiles-card-display, var(--tiles-default-card-display));
          visibility: var(--tiles-card-visibility, var(--tiles-default-card-visibility));
          color: var(--tiles-card-title-color, var(--tiles-default-card-title-color));
          text-align: var(--tiles-card-title-align, var(--tiles-default-card-title-align));
          background: var(--tiles-card-background, var(--tiles-default-card-background));
          background-size: var(--tiles-default-card-background-size);
          background-repeat: var(--tiles-default-card-background-repeat);
      }
      
      .grid {
          display: var(--tiles-default-card-grid-display);
          grid-template-columns: repeat(var(--tiles-card-columns, var(--tiles-default-card-columns)), var(--tiles-card-column-width, var(--tiles-default-card-column-width)));
          grid-auto-rows: var(--tiles-card-row-height, var(--tiles-default-card-row-height));
          grid-gap: var(--tiles-card-gap, var(--tiles-default-card-gap));
          padding: var(--tiles-card-padding, var(--tiles-default-card-padding));
          padding-top: var(--tiles-card-padding-top, var(--tiles-card-padding, var(--tiles-default-card-padding)));
          justify-content: var(--tiles-card-align, var(--tiles-default-card-align));
      }
      
      tiles-listbox {
          /* height: 100%;
          width: 100%; */
          grid-area: var(--tiles-grid-area, var(--tiles-default-grid-area));
          display: var(--tiles-display, var(--tiles-default-display));
          visibility: var(--tiles-visibility, var(--tiles-default-visibility));
          background: var(--tiles-background, var(--tiles-default-background));
          box-shadow: var(--tiles-box-shadow, var(--tiles-default-box-shadow)) !important;
          margin: var(--tiles-default-margin) !important;
          min-width: var(--tiles-default-min-width);
          min-height: var(--tiles-default-min-height);
          flex-direction: var(--tiles-orientation, var(--tiles-default-listbox-orientation));
          align-items: var(--tiles-vertical-align, var(--tiles-default-vertical-align));
          justify-content: var(--tiles-horizontal-align, var(--tiles-default-horizontal-align));
          opacity: var(--tiles-opacity, var(--tiles-default-opacity));
          border-style: var(--tiles-border-style, var(--tiles-default-border-style));
          border-width: var(--tiles-border-size, var(--tiles-default-border-size));
          border-color: var(--tiles-border-color, var(--tiles-default-contents-color));
          border-radius: var(--tiles-border-radius, var(--tiles-default-border-radius));
          padding: var(--tiles-default-listbox-padding);
          -webkit-filter: grayscale(var(--tiles-grayscale, var(--tiles-default-grayscale))); /* Google Chrome, Safari 6+ & Opera 15+ */
          filter: grayscale(var(--tiles-grayscale, var(--tiles-default-grayscale))); /* Microsoft Edge and Firefox 35+ */
      }
      
      tiles-listbox .icon {
          height: var(--tiles-icon-size, var(--tiles-default-icon-size));
          width: var(--tiles-icon-size, var(--tiles-default-icon-size));
          padding: var(--tiles-icon-padding, var(--tiles-default-icon-padding));
          --iron-icon-fill-color: var(--tiles-icon-color, var(--tiles-default-contents-color));
          --iron-icon-height: var(--tiles-icon-size, var(--tiles-default-icon-size));
          --iron-icon-width: var(--tiles-icon-size, var(--tiles-default-icon-size));
      }
      
      tiles-listbox.disabled {
          background: var(--tiles-background-disabled, var(--tiles-default-background-disabled));
          opacity: var(--tiles-opacity-disabled, var(--tiles-default-opacity-disabled));
          border-color: var(--tiles-border-color-disabled, var(--tiles-default-border-color-disabled));
      
          -webkit-filter: grayscale(var(--tiles-grayscale-disabled, var(--tiles-default-grayscale-disabled))); /* Google Chrome, Safari 6+ & Opera 15+ */
          filter: grayscale(var(--tiles-grayscale-disabled, var(--tiles-default-grayscale-disabled))); /* Microsoft Edge and Firefox 35+ */
      }
      
      tiles-listbox paper-dropdown-menu {
          width: var(--tiles-default-dropdownmenu-width);
          padding: var(--tiles-dropdownmenu-padding, var(--tiles-default-dropdownmenu-padding)); /* top|right|bottom|left */
          text-transform: var(--tiles-listbox-title-transform, var(--tiles-default-listbox-title-transform));
      
          --paper-input-container-color: var(--tiles-listbox-title-color, var(--tiles-default-listbox-title-color));
          --iron-icon-fill-color: var(--tiles-listbox-title-color, var(--tiles-default-listbox-title-color));
          --paper-listbox-background-color: var(--tiles-listbox-background-list-color, var(--tiles-default-listbox-background-list-color));
          --paper-listbox-color: var(--tiles-listbox-itens-color, var(--tiles-default-listbox-itens-color));
          --paper-input-container-focus-color: var(--tiles-background, var(--tiles-default-background));
      }
      
      tiles-listbox paper-item {
          font-size: var(--tiles-listbox-itens-size, var(--tiles-default-listbox-itens-size));
          text-transform: var(--tiles-listbox-itens-transform, var(--tiles-default-listbox-itens-transform));
      }
      
      paper-button {
          height: 100%;
          width: 100%;
          grid-area: var(--tiles-grid-area, var(--tiles-default-grid-area));
          display: var(--tiles-display, var(--tiles-default-display));
          visibility: var(--tiles-visibility, var(--tiles-default-visibility));
          background: var(--tiles-background, var(--tiles-default-background));
          background-size: var(--tiles-image-size, var(--tiles-default-image-size));
          background-repeat: no-repeat;
          background-position: 50% 50%;
          box-shadow: var(--tiles-box-shadow, var(--tiles-default-box-shadow)) !important;
          margin: var(--tiles-default-margin) !important;
          min-width: var(--tiles-default-min-width);
          min-height: var(--tiles-default-min-height);
          flex-direction: var(--tiles-orientation, var(--tiles-default-orientation));
          align-items: var(--tiles-vertical-align, var(--tiles-default-vertical-align));
          justify-content: var(--tiles-horizontal-align, var(--tiles-default-horizontal-align));
          opacity: var(--tiles-opacity, --tiles-default-opacity);
          border-style: var(--tiles-border-style, var(--tiles-default-border-style));
          border-width: var(--tiles-border-size, var(--tiles-default-border-size));
          border-color: var(--tiles-border-color, var(--tiles-default-contents-color));
          border-radius: var(--tiles-border-radius, var(--tiles-default-border-radius));
          padding: var(--tiles-padding, var(--tiles-default-padding));
          color: var(--tiles-label-color, var(--tiles-default-contents-color));
          font-size: var(--tiles-label-size, var(--tiles-default-labels-size));
          -webkit-filter: grayscale(var(--tiles-grayscale, var(--tiles-default-grayscale))); /* Google Chrome, Safari 6+ & Opera 15+ */
          filter: grayscale(var(--tiles-grayscale, var(--tiles-default-grayscale))); /* Microsoft Edge and Firefox 35+ */
          text-align: var(--tiles-text-align, var(--tiles-default-text-align));
      
          --iron-icon-fill-color: var(--tiles-icon-color, var(--tiles-label-color, var(--tiles-default-contents-color)));
          --iron-icon-height: var(--tiles-icon-size, var(--tiles-default-icon-size));
          --iron-icon-width: var(--tiles-icon-size, var(--tiles-default-icon-size));
      }
      
      paper-button.on {
          background: var(--tiles-background-on, var(--tiles-background, var(--google-green-500)));
          background-repeat: no-repeat;
          background-position: 50% 50%;
          background-size: var(--tiles-image-size,  var(--tiles-default-image-size));
          opacity: var(--tiles-opacity-on, var(--tiles-opacity, --tiles-default-opacity));
          color: var(--tiles-label-color-on, var(--tiles-label-color, var(--tiles-default-contents-color)));
          border-color: var(--tiles-border-color-on, var(--tiles-border-color, var(--tiles-default-contents-color)));
          /* --iron-icon-stroke-color: 	Stroke color of the svg icon */
          --iron-icon-fill-color: var(--tiles-icon-color-on, var(--tiles-icon-color, var(--tiles-default-contents-color)));
      
          -webkit-filter: grayscale(var(--tiles-grayscale-on, var(--tiles-grayscale, var(--tiles-default-grayscale)))); /* Google Chrome, Safari 6+ & Opera 15+ */
          filter: grayscale(var(--tiles-grayscale-on, var(--tiles-grayscale, var(--tiles-default-grayscale)))); /* Microsoft Edge and Firefox 35+ */
      }
      
      paper-button.off {
          background: var(--tiles-background-off, var(--tiles-background, var(--google-red-500)));
          background-repeat: no-repeat;
          background-position: 50% 50%;
          background-size: var(--tiles-image-size,  var(--tiles-default-image-size));
          opacity: var(--tiles-opacity-off, var(--tiles-opacity, --tiles-default-opacity));
          color: var(--tiles-label-color-off, var(--tiles-label-color, var(--tiles-default-contents-color)));
          border-color: var(--tiles-border-color-off, var(--tiles-border-color, var(--tiles-default-contents-color)));
          /* --iron-icon-stroke-color: 	Stroke color of the svg icon */
          --iron-icon-fill-color: var(--tiles-icon-color-off, var(--tiles-icon-color, var(--tiles-default-contents-color)));
      
          -webkit-filter: grayscale(var(--tiles-grayscale-off, var(--tiles-grayscale, var(--tiles-default-grayscale)))); /* Google Chrome, Safari 6+ & Opera 15+ */
          filter: grayscale(var(--tiles-grayscale-off, var(--tiles-grayscale, var(--tiles-default-grayscale)))); /* Microsoft Edge and Firefox 35+ */
      
      }
      
      paper-button.disabled {
          background: var(--tiles-background-disabled, var(--tiles-background, var(--primary-color)));
          background-repeat: no-repeat;
          background-position: 50% 50%;
          background-size: var(--tiles-image-size,  var(--tiles-default-image-size));
          opacity: var(--tiles-opacity-disabled, var(--tiles-opacity, --tiles-default-opacity));
          color: var(--tiles-label-color-disabled, var(--tiles-label-color, var(--tiles-default-contents-color)));
          border-color: var(--tiles-border-color-disabled, var(--tiles-border-color, var(--tiles-default-contents-color)));
          /* --iron-icon-stroke-color: 	Stroke color of the svg icon */
          --iron-icon-fill-color: var(--tiles-icon-color-disabled, var(--tiles-icon-color, var(--tiles-default-contents-color)));
      
          -webkit-filter: grayscale(var(--tiles-grayscale-disabled, var(--tiles-grayscale, var(--tiles-default-grayscale-disabled)))); /* Google Chrome, Safari 6+ & Opera 15+ */
          filter: grayscale(var(--tiles-grayscale-disabled, var(--tiles-grayscale, var(--tiles-default-grayscale-disabled)))); /* Microsoft Edge and Firefox 35+ */
      }
      
      paper-button .icon {
          padding: var(--tiles-icon-padding, var(--tiles-default-icon-padding));
      }
      
      paper-button .label {
          color: var(--tiles-label-color, var(--tiles-default-contents-color));
          font-size: var(--tiles-label-size, var(--tiles-default-labels-size));
          text-transform: var(--tiles-label-transform, none);
          padding: var(--tiles-label-padding, var(--tiles-default-labels-padding));
      }
      
      paper-button.on .label {
          color: var(--tiles-label-color-on, var(--tiles-label-color, var(--tiles-default-contents-color)));
      }
      
      paper-button.off .label {
          color: var(--tiles-label-color-off, var(--tiles-label-color, var(--tiles-default-contents-color)));
      }
      
      paper-button.disabled .label {
          color: var(--tiles-label-color-disabled, var(--tiles-label-color, var(--tiles-default-contents-color)));
      }
      
      paper-button .labelSec {
          color: var(--tiles-label-sec-color, var(--tiles-default-contents-color));
          font-size: var(--tiles-label-sec-size, var(--tiles-default-labels-size));
          text-transform: var(--tiles-label-sec-transform, none);
          padding: var(--tiles-label-sec-padding, var(--tiles-default-labels-padding));
      }
      
      paper-button.on .labelSec {
          color: var(--tiles-label-sec-color-on, var(--tiles-label-sec-color, var(--tiles-default-contents-color)));
      }
      
      paper-button.off .labelSec {
          color: var(--tiles-label-sec-color-off, var(--tiles-label-sec-color, var(--tiles-default-contents-color)));
      }
      
      paper-button.disabled .labelSec {
          color: var(--tiles-label-sec-color-disabled, var(--tiles-label-sec-color, var(--tiles-default-contents-color)));
      }
  `;
  }

}
  
customElements.define('tiles-card', TilesCard);