!function(t,e){"object"==typeof exports&&"undefined"!=typeof module?module.exports=e():"function"==typeof define&&define.amd?define(e):(t=t||self).BannerCard=e()}(this,function(){"use strict";const t=new WeakMap,e=e=>"function"==typeof e&&t.has(e),i=void 0!==window.customElements&&void 0!==window.customElements.polyfillWrapFlushCallback,s=(t,e,i=null)=>{let s=e;for(;s!==i;){const e=s.nextSibling;t.removeChild(s),s=e}},n={},r={},o=`{{lit-${String(Math.random()).slice(2)}}}`,a=`\x3c!--${o}--\x3e`,l=new RegExp(`${o}|${a}`),c="$lit$";class h{constructor(t,e){this.parts=[],this.element=e;let i=-1,s=0;const n=[],r=e=>{const a=e.content,h=document.createTreeWalker(a,133,null,!1);let d=0;for(;h.nextNode();){i++;const e=h.currentNode;if(1===e.nodeType){if(e.hasAttributes()){const n=e.attributes;let r=0;for(let t=0;t<n.length;t++)n[t].value.indexOf(o)>=0&&r++;for(;r-- >0;){const n=t.strings[s],r=u.exec(n)[2],o=r.toLowerCase()+c,a=e.getAttribute(o).split(l);this.parts.push({type:"attribute",index:i,name:r,strings:a}),e.removeAttribute(o),s+=a.length-1}}"TEMPLATE"===e.tagName&&r(e)}else if(3===e.nodeType){const t=e.data;if(t.indexOf(o)>=0){const r=e.parentNode,o=t.split(l),a=o.length-1;for(let t=0;t<a;t++)r.insertBefore(""===o[t]?p():document.createTextNode(o[t]),e),this.parts.push({type:"node",index:++i});""===o[a]?(r.insertBefore(p(),e),n.push(e)):e.data=o[a],s+=a}}else if(8===e.nodeType)if(e.data===o){const t=e.parentNode;null!==e.previousSibling&&i!==d||(i++,t.insertBefore(p(),e)),d=i,this.parts.push({type:"node",index:i}),null===e.nextSibling?e.data="":(n.push(e),i--),s++}else{let t=-1;for(;-1!==(t=e.data.indexOf(o,t+1));)this.parts.push({type:"node",index:-1})}}};r(e);for(const t of n)t.parentNode.removeChild(t)}}const d=t=>-1!==t.index,p=()=>document.createComment(""),u=/([ \x09\x0a\x0c\x0d])([^\0-\x1F\x7F-\x9F \x09\x0a\x0c\x0d"'>=\/]+)([ \x09\x0a\x0c\x0d]*=[ \x09\x0a\x0c\x0d]*(?:[^ \x09\x0a\x0c\x0d"'`<>=]*|"[^"]*|'[^']*))$/;class m{constructor(t,e,i){this._parts=[],this.template=t,this.processor=e,this.options=i}update(t){let e=0;for(const i of this._parts)void 0!==i&&i.setValue(t[e]),e++;for(const t of this._parts)void 0!==t&&t.commit()}_clone(){const t=i?this.template.element.content.cloneNode(!0):document.importNode(this.template.element.content,!0),e=this.template.parts;let s=0,n=0;const r=t=>{const i=document.createTreeWalker(t,133,null,!1);let o=i.nextNode();for(;s<e.length&&null!==o;){const t=e[s];if(d(t))if(n===t.index){if("node"===t.type){const t=this.processor.handleTextExpression(this.options);t.insertAfterNode(o.previousSibling),this._parts.push(t)}else this._parts.push(...this.processor.handleAttributeExpressions(o,t.name,t.strings,this.options));s++}else n++,"TEMPLATE"===o.nodeName&&r(o.content),o=i.nextNode();else this._parts.push(void 0),s++}};return r(t),i&&(document.adoptNode(t),customElements.upgrade(t)),t}}class g{constructor(t,e,i,s){this.strings=t,this.values=e,this.type=i,this.processor=s}getHTML(){const t=this.strings.length-1;let e="";for(let i=0;i<t;i++){const t=this.strings[i],s=u.exec(t);e+=s?t.substr(0,s.index)+s[1]+s[2]+c+s[3]+o:t+a}return e+this.strings[t]}getTemplateElement(){const t=document.createElement("template");return t.innerHTML=this.getHTML(),t}}const f=t=>null===t||!("object"==typeof t||"function"==typeof t);class y{constructor(t,e,i){this.dirty=!0,this.element=t,this.name=e,this.strings=i,this.parts=[];for(let t=0;t<i.length-1;t++)this.parts[t]=this._createPart()}_createPart(){return new v(this)}_getValue(){const t=this.strings,e=t.length-1;let i="";for(let s=0;s<e;s++){i+=t[s];const e=this.parts[s];if(void 0!==e){const t=e.value;if(null!=t&&(Array.isArray(t)||"string"!=typeof t&&t[Symbol.iterator]))for(const e of t)i+="string"==typeof e?e:String(e);else i+="string"==typeof t?t:String(t)}}return i+=t[e]}commit(){this.dirty&&(this.dirty=!1,this.element.setAttribute(this.name,this._getValue()))}}class v{constructor(t){this.value=void 0,this.committer=t}setValue(t){t===n||f(t)&&t===this.value||(this.value=t,e(t)||(this.committer.dirty=!0))}commit(){for(;e(this.value);){const t=this.value;this.value=n,t(this)}this.value!==n&&this.committer.commit()}}class _{constructor(t){this.value=void 0,this._pendingValue=void 0,this.options=t}appendInto(t){this.startNode=t.appendChild(p()),this.endNode=t.appendChild(p())}insertAfterNode(t){this.startNode=t,this.endNode=t.nextSibling}appendIntoPart(t){t._insert(this.startNode=p()),t._insert(this.endNode=p())}insertAfterPart(t){t._insert(this.startNode=p()),this.endNode=t.endNode,t.endNode=this.startNode}setValue(t){this._pendingValue=t}commit(){for(;e(this._pendingValue);){const t=this._pendingValue;this._pendingValue=n,t(this)}const t=this._pendingValue;t!==n&&(f(t)?t!==this.value&&this._commitText(t):t instanceof g?this._commitTemplateResult(t):t instanceof Node?this._commitNode(t):Array.isArray(t)||t[Symbol.iterator]?this._commitIterable(t):t===r?(this.value=r,this.clear()):this._commitText(t))}_insert(t){this.endNode.parentNode.insertBefore(t,this.endNode)}_commitNode(t){this.value!==t&&(this.clear(),this._insert(t),this.value=t)}_commitText(t){const e=this.startNode.nextSibling;t=null==t?"":t,e===this.endNode.previousSibling&&3===e.nodeType?e.data=t:this._commitNode(document.createTextNode("string"==typeof t?t:String(t))),this.value=t}_commitTemplateResult(t){const e=this.options.templateFactory(t);if(this.value instanceof m&&this.value.template===e)this.value.update(t.values);else{const i=new m(e,t.processor,this.options),s=i._clone();i.update(t.values),this._commitNode(s),this.value=i}}_commitIterable(t){Array.isArray(this.value)||(this.value=[],this.clear());const e=this.value;let i,s=0;for(const n of t)void 0===(i=e[s])&&(i=new _(this.options),e.push(i),0===s?i.appendIntoPart(this):i.insertAfterPart(e[s-1])),i.setValue(n),i.commit(),s++;s<e.length&&(e.length=s,this.clear(i&&i.endNode))}clear(t=this.startNode){s(this.startNode.parentNode,t.nextSibling,this.endNode)}}class b{constructor(t,e,i){if(this.value=void 0,this._pendingValue=void 0,2!==i.length||""!==i[0]||""!==i[1])throw new Error("Boolean attributes can only contain a single expression");this.element=t,this.name=e,this.strings=i}setValue(t){this._pendingValue=t}commit(){for(;e(this._pendingValue);){const t=this._pendingValue;this._pendingValue=n,t(this)}if(this._pendingValue===n)return;const t=!!this._pendingValue;this.value!==t&&(t?this.element.setAttribute(this.name,""):this.element.removeAttribute(this.name)),this.value=t,this._pendingValue=n}}class w extends y{constructor(t,e,i){super(t,e,i),this.single=2===i.length&&""===i[0]&&""===i[1]}_createPart(){return new S(this)}_getValue(){return this.single?this.parts[0].value:super._getValue()}commit(){this.dirty&&(this.dirty=!1,this.element[this.name]=this._getValue())}}class S extends v{}let x=!1;try{const t={get capture(){return x=!0,!1}};window.addEventListener("test",t,t),window.removeEventListener("test",t,t)}catch(t){}class C{constructor(t,e,i){this.value=void 0,this._pendingValue=void 0,this.element=t,this.eventName=e,this.eventContext=i,this._boundHandleEvent=t=>this.handleEvent(t)}setValue(t){this._pendingValue=t}commit(){for(;e(this._pendingValue);){const t=this._pendingValue;this._pendingValue=n,t(this)}if(this._pendingValue===n)return;const t=this._pendingValue,i=this.value,s=null==t||null!=i&&(t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive),r=null!=t&&(null==i||s);s&&this.element.removeEventListener(this.eventName,this._boundHandleEvent,this._options),r&&(this._options=P(t),this.element.addEventListener(this.eventName,this._boundHandleEvent,this._options)),this.value=t,this._pendingValue=n}handleEvent(t){"function"==typeof this.value?this.value.call(this.eventContext||this.element,t):this.value.handleEvent(t)}}const P=t=>t&&(x?{capture:t.capture,passive:t.passive,once:t.once}:t.capture);const k=new class{handleAttributeExpressions(t,e,i,s){const n=e[0];return"."===n?new w(t,e.slice(1),i).parts:"@"===n?[new C(t,e.slice(1),s.eventContext)]:"?"===n?[new b(t,e.slice(1),i)]:new y(t,e,i).parts}handleTextExpression(t){return new _(t)}};function $(t){let e=N.get(t.type);void 0===e&&(e={stringsArray:new WeakMap,keyString:new Map},N.set(t.type,e));let i=e.stringsArray.get(t.strings);if(void 0!==i)return i;const s=t.strings.join(o);return void 0===(i=e.keyString.get(s))&&(i=new h(t,t.getTemplateElement()),e.keyString.set(s,i)),e.stringsArray.set(t.strings,i),i}const N=new Map,A=new WeakMap;(window.litHtmlVersions||(window.litHtmlVersions=[])).push("1.0.0");const E=(t,...e)=>new g(t,e,"html",k),z=133;function T(t,e){const{element:{content:i},parts:s}=t,n=document.createTreeWalker(i,z,null,!1);let r=O(s),o=s[r],a=-1,l=0;const c=[];let h=null;for(;n.nextNode();){a++;const t=n.currentNode;for(t.previousSibling===h&&(h=null),e.has(t)&&(c.push(t),null===h&&(h=t)),null!==h&&l++;void 0!==o&&o.index===a;)o.index=null!==h?-1:o.index-l,o=s[r=O(s,r)]}c.forEach(t=>t.parentNode.removeChild(t))}const V=t=>{let e=11===t.nodeType?0:1;const i=document.createTreeWalker(t,z,null,!1);for(;i.nextNode();)e++;return e},O=(t,e=-1)=>{for(let i=e+1;i<t.length;i++){const e=t[i];if(d(e))return i}return-1};const M=(t,e)=>`${t}--${e}`;let R=!0;void 0===window.ShadyCSS?R=!1:void 0===window.ShadyCSS.prepareTemplateDom&&(console.warn("Incompatible ShadyCSS version detected.Please update to at least @webcomponents/webcomponentsjs@2.0.2 and@webcomponents/shadycss@1.3.1."),R=!1);const j=t=>e=>{const i=M(e.type,t);let s=N.get(i);void 0===s&&(s={stringsArray:new WeakMap,keyString:new Map},N.set(i,s));let n=s.stringsArray.get(e.strings);if(void 0!==n)return n;const r=e.strings.join(o);if(void 0===(n=s.keyString.get(r))){const i=e.getTemplateElement();R&&window.ShadyCSS.prepareTemplateDom(i,t),n=new h(e,i),s.keyString.set(r,n)}return s.stringsArray.set(e.strings,n),n},U=["html","svg"],D=new Set,q=(t,e,i)=>{D.add(i);const s=t.querySelectorAll("style");if(0===s.length)return void window.ShadyCSS.prepareTemplateStyles(e.element,i);const n=document.createElement("style");for(let t=0;t<s.length;t++){const e=s[t];e.parentNode.removeChild(e),n.textContent+=e.textContent}if((t=>{U.forEach(e=>{const i=N.get(M(e,t));void 0!==i&&i.keyString.forEach(t=>{const{element:{content:e}}=t,i=new Set;Array.from(e.querySelectorAll("style")).forEach(t=>{i.add(t)}),T(t,i)})})})(i),function(t,e,i=null){const{element:{content:s},parts:n}=t;if(null==i)return void s.appendChild(e);const r=document.createTreeWalker(s,z,null,!1);let o=O(n),a=0,l=-1;for(;r.nextNode();)for(l++,r.currentNode===i&&(a=V(e),i.parentNode.insertBefore(e,i));-1!==o&&n[o].index===l;){if(a>0){for(;-1!==o;)n[o].index+=a,o=O(n,o);return}o=O(n,o)}}(e,n,e.element.content.firstChild),window.ShadyCSS.prepareTemplateStyles(e.element,i),window.ShadyCSS.nativeShadow){const i=e.element.content.querySelector("style");t.insertBefore(i.cloneNode(!0),t.firstChild)}else{e.element.content.insertBefore(n,e.element.content.firstChild);const t=new Set;t.add(n),T(e,t)}};window.JSCompiler_renameProperty=(t,e)=>t;const L={toAttribute(t,e){switch(e){case Boolean:return t?"":null;case Object:case Array:return null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){switch(e){case Boolean:return null!==t;case Number:return null===t?null:Number(t);case Object:case Array:return JSON.parse(t)}return t}},F=(t,e)=>e!==t&&(e==e||t==t),H={attribute:!0,type:String,converter:L,reflect:!1,hasChanged:F},B=Promise.resolve(!0),I=1,W=4,J=8,Y=16,G=32;class K extends HTMLElement{constructor(){super(),this._updateState=0,this._instanceProperties=void 0,this._updatePromise=B,this._hasConnectedResolver=void 0,this._changedProperties=new Map,this._reflectingProperties=void 0,this.initialize()}static get observedAttributes(){this.finalize();const t=[];return this._classProperties.forEach((e,i)=>{const s=this._attributeNameForProperty(i,e);void 0!==s&&(this._attributeToPropertyMap.set(s,i),t.push(s))}),t}static _ensureClassProperties(){if(!this.hasOwnProperty(JSCompiler_renameProperty("_classProperties",this))){this._classProperties=new Map;const t=Object.getPrototypeOf(this)._classProperties;void 0!==t&&t.forEach((t,e)=>this._classProperties.set(e,t))}}static createProperty(t,e=H){if(this._ensureClassProperties(),this._classProperties.set(t,e),e.noAccessor||this.prototype.hasOwnProperty(t))return;const i="symbol"==typeof t?Symbol():`__${t}`;Object.defineProperty(this.prototype,t,{get(){return this[i]},set(e){const s=this[t];this[i]=e,this._requestUpdate(t,s)},configurable:!0,enumerable:!0})}static finalize(){if(this.hasOwnProperty(JSCompiler_renameProperty("finalized",this))&&this.finalized)return;const t=Object.getPrototypeOf(this);if("function"==typeof t.finalize&&t.finalize(),this.finalized=!0,this._ensureClassProperties(),this._attributeToPropertyMap=new Map,this.hasOwnProperty(JSCompiler_renameProperty("properties",this))){const t=this.properties,e=[...Object.getOwnPropertyNames(t),..."function"==typeof Object.getOwnPropertySymbols?Object.getOwnPropertySymbols(t):[]];for(const i of e)this.createProperty(i,t[i])}}static _attributeNameForProperty(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}static _valueHasChanged(t,e,i=F){return i(t,e)}static _propertyValueFromAttribute(t,e){const i=e.type,s=e.converter||L,n="function"==typeof s?s:s.fromAttribute;return n?n(t,i):t}static _propertyValueToAttribute(t,e){if(void 0===e.reflect)return;const i=e.type,s=e.converter;return(s&&s.toAttribute||L.toAttribute)(t,i)}initialize(){this._saveInstanceProperties(),this._requestUpdate()}_saveInstanceProperties(){this.constructor._classProperties.forEach((t,e)=>{if(this.hasOwnProperty(e)){const t=this[e];delete this[e],this._instanceProperties||(this._instanceProperties=new Map),this._instanceProperties.set(e,t)}})}_applyInstanceProperties(){this._instanceProperties.forEach((t,e)=>this[e]=t),this._instanceProperties=void 0}connectedCallback(){this._updateState=this._updateState|G,this._hasConnectedResolver&&(this._hasConnectedResolver(),this._hasConnectedResolver=void 0)}disconnectedCallback(){}attributeChangedCallback(t,e,i){e!==i&&this._attributeToProperty(t,i)}_propertyToAttribute(t,e,i=H){const s=this.constructor,n=s._attributeNameForProperty(t,i);if(void 0!==n){const t=s._propertyValueToAttribute(e,i);if(void 0===t)return;this._updateState=this._updateState|J,null==t?this.removeAttribute(n):this.setAttribute(n,t),this._updateState=this._updateState&~J}}_attributeToProperty(t,e){if(this._updateState&J)return;const i=this.constructor,s=i._attributeToPropertyMap.get(t);if(void 0!==s){const t=i._classProperties.get(s)||H;this._updateState=this._updateState|Y,this[s]=i._propertyValueFromAttribute(e,t),this._updateState=this._updateState&~Y}}_requestUpdate(t,e){let i=!0;if(void 0!==t){const s=this.constructor,n=s._classProperties.get(t)||H;s._valueHasChanged(this[t],e,n.hasChanged)?(this._changedProperties.has(t)||this._changedProperties.set(t,e),!0!==n.reflect||this._updateState&Y||(void 0===this._reflectingProperties&&(this._reflectingProperties=new Map),this._reflectingProperties.set(t,n))):i=!1}!this._hasRequestedUpdate&&i&&this._enqueueUpdate()}requestUpdate(t,e){return this._requestUpdate(t,e),this.updateComplete}async _enqueueUpdate(){let t,e;this._updateState=this._updateState|W;const i=this._updatePromise;this._updatePromise=new Promise((i,s)=>{t=i,e=s});try{await i}catch(t){}this._hasConnected||await new Promise(t=>this._hasConnectedResolver=t);try{const t=this.performUpdate();null!=t&&await t}catch(t){e(t)}t(!this._hasRequestedUpdate)}get _hasConnected(){return this._updateState&G}get _hasRequestedUpdate(){return this._updateState&W}get hasUpdated(){return this._updateState&I}performUpdate(){this._instanceProperties&&this._applyInstanceProperties();let t=!1;const e=this._changedProperties;try{(t=this.shouldUpdate(e))&&this.update(e)}catch(e){throw t=!1,e}finally{this._markUpdated()}t&&(this._updateState&I||(this._updateState=this._updateState|I,this.firstUpdated(e)),this.updated(e))}_markUpdated(){this._changedProperties=new Map,this._updateState=this._updateState&~W}get updateComplete(){return this._updatePromise}shouldUpdate(t){return!0}update(t){void 0!==this._reflectingProperties&&this._reflectingProperties.size>0&&(this._reflectingProperties.forEach((t,e)=>this._propertyToAttribute(e,this[e],t)),this._reflectingProperties=void 0)}updated(t){}firstUpdated(t){}}K.finalized=!0;const Q="adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,X=Symbol();class Z{constructor(t,e){if(e!==X)throw new Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t}get styleSheet(){return void 0===this._styleSheet&&(Q?(this._styleSheet=new CSSStyleSheet,this._styleSheet.replaceSync(this.cssText)):this._styleSheet=null),this._styleSheet}toString(){return this.cssText}}(window.litElementVersions||(window.litElementVersions=[])).push("2.0.1");const tt=t=>t.flat?t.flat(1/0):function t(e,i=[]){for(let s=0,n=e.length;s<n;s++){const n=e[s];Array.isArray(n)?t(n,i):i.push(n)}return i}(t);class et extends K{static finalize(){super.finalize(),this._styles=this.hasOwnProperty(JSCompiler_renameProperty("styles",this))?this._getUniqueStyles():this._styles||[]}static _getUniqueStyles(){const t=this.styles,e=[];if(Array.isArray(t)){tt(t).reduceRight((t,e)=>(t.add(e),t),new Set).forEach(t=>e.unshift(t))}else t&&e.push(t);return e}initialize(){super.initialize(),this.renderRoot=this.createRenderRoot(),window.ShadowRoot&&this.renderRoot instanceof window.ShadowRoot&&this.adoptStyles()}createRenderRoot(){return this.attachShadow({mode:"open"})}adoptStyles(){const t=this.constructor._styles;0!==t.length&&(void 0===window.ShadyCSS||window.ShadyCSS.nativeShadow?Q?this.renderRoot.adoptedStyleSheets=t.map(t=>t.styleSheet):this._needsShimAdoptedStyleSheets=!0:window.ShadyCSS.ScopingShim.prepareAdoptedCssText(t.map(t=>t.cssText),this.localName))}connectedCallback(){super.connectedCallback(),this.hasUpdated&&void 0!==window.ShadyCSS&&window.ShadyCSS.styleElement(this)}update(t){super.update(t);const e=this.render();e instanceof g&&this.constructor.render(e,this.renderRoot,{scopeName:this.localName,eventContext:this}),this._needsShimAdoptedStyleSheets&&(this._needsShimAdoptedStyleSheets=!1,this.constructor._styles.forEach(t=>{const e=document.createElement("style");e.textContent=t.cssText,this.renderRoot.appendChild(e)}))}render(){}}et.finalized=!0,et.render=(t,e,i)=>{const n=i.scopeName,r=A.has(e),o=e instanceof ShadowRoot&&R&&t instanceof g,a=o&&!D.has(n),l=a?document.createDocumentFragment():e;if(((t,e,i)=>{let n=A.get(e);void 0===n&&(s(e,e.firstChild),A.set(e,n=new _(Object.assign({templateFactory:$},i))),n.appendInto(e)),n.setValue(t),n.commit()})(t,l,Object.assign({templateFactory:j(n)},i)),a){const t=A.get(l);A.delete(l),t.value instanceof m&&q(l,t.value.template,n),s(e,e.firstChild),e.appendChild(l),A.set(e,t)}!r&&o&&window.ShadyCSS.styleElement(e.host)};var it=((t,...e)=>{const i=e.reduce((e,i,s)=>e+(t=>{if(t instanceof Z)return t.cssText;throw new Error(`Value passed to 'css' function must be a 'css' function result: ${t}. Use 'unsafeCSS' to pass non-literal values, but\n            take care to ensure page security.`)})(i)+t[s+1],t[0]);return new Z(i,X)})`
  :host {
    --bc-error-color: var(--lumo-error-color);
    --bc-font-size-heading: 3em;
    --bc-font-size-entity-value: 1.5em;
    --bc-font-size-media-title: 0.9em;
    --bc-spacing: 4px;
    --bc-button-size: 32px;
  }
  ha-card {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  paper-icon-button {
    width: var(--bc-button-size);
    height: var(--bc-button-size);
    padding: var(--bc-spacing);
  }

  ha-card.not-found {
    background-color: var(--lumo-error-color);
  }

  .heading {
    display: block;
    font-size: var(--bc-font-size-heading);
    font-weight: 300;
    cursor: pointer;
    align-self: stretch;
    text-align: center;
    color: var(--primary-text-color);
  }

  .overlay-strip {
    background: rgba(0, 0, 0, 0.3);
    overflow: hidden;
    width: 100%;
  }

  .error {
    display: flex;
    padding: calc(var(--bc-spacing) * 4)
    color: white;
    width: 100%;
    justify-content: center;
    align-items: center;
    font-weight: 700;
    font-size: 1.4rem;
  }
  .entities {
    padding: calc(var(--bc-spacing) * 2) 0px;
    color: white;
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    flex-wrap: wrap;
    margin-left: -1px;
  }

  .entity-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: calc(var(--bc-spacing) * 2) 0;
    box-shadow: -1px 0px 0 0 white;
  }

  .media-title {
    flex: 1 0 ;
    overflow: hidden;
    font-weight: 300;
    font-size: var(--bc-font-size-media-title);
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .media-controls {
    display: flex;
    flex: 0 0 calc(var(--bc-button-size) * 3);
  }

  .entity-state.expand .entity-value {
    width: 100%;
  }

  .entity-state-left {
    margin-right: auto;
    margin-left: 16px;
  }

  .entity-state-right {
    margin-left: auto;
    margin-right: 16px;
  }

  .entity-name {
    font-weight: 700;
    white-space: nowrap;
  }

  .entity-value {
    display: flex;
    width: 100%;
    flex: 1 0;
    padding-top: var(--bc-spacing);
    font-size: var(--bc-font-size-entity-value);
    align-items: center;
    justify-content: center;
  }

  .entity-value ha-icon {
    color: white;
  }

  .toggle {
    cursor: pointer;
    --paper-toggle-button-unchecked-bar-color: rgba(255, 255, 255, 0.4);
    --paper-toggle-button-unchecked-button-color: rgba(255, 255, 255, 0.4);
    --paper-toggle-button-unchecked-ink-color: rgba(1, 1, 1, 0.6);

    --paper-toggle-button-checked-bar-color: white;
    --paper-toggle-button-checked-button-color: white;
    --paper-toggle-button-checked-ink-color: white;
  }

  mwc-button {
    --mdc-theme-primary: white;
  }

`;function st({state:t,attributes:e},i=!1){return"string"==typeof i&&e.hasOwnProperty(i)?e[i]:t}function nt(t){return"object"==typeof t?(e=t,i=t=>!1===t?null:t,Object.entries(e).reduce((t,[e,s])=>({...t,[e]:i(s,e)}),{})):{entity:t};var e,i}const rt={"=":(t,e)=>e.includes(t),">":(t,e)=>t>e[0],"<":(t,e)=>t<e[0],"!=":(t,e)=>!e.includes(t)};function ot(t,e){if(["string","number","boolean"].includes(typeof t))return rt["="](e,[t]);if(Array.isArray(t)){const[i,...s]=t;return rt.hasOwnProperty(i)?rt[i](e,s):rt["="](e,s)}throw new Error(`Couldn't find a valid matching strategy for '${t}'`)}const at=/^(mdi|hass):/;function lt(t){return"string"==typeof t&&t.match(at)}class ct extends et{static get properties(){return{config:Object,gridSizes:Array,entities:Array,entityValues:Array,error:String,rowSize:Number,_hass:Object}}static get styles(){return[it]}constructor(){super(),this.config={},this.entities=[],this.error=null,this._hass={}}setConfig(t){if(void 0===t.heading)throw new Error("You need to define a heading");if(this.entities=(t.entities||[]).map(nt),this.config=t,void 0!==t.row_size){if(t.row_size<1)throw new Error("row_size must be at least 1");this.rowSize=t.row_size}this.rowSize=this.rowSize||3,this.gridSizes=Array(this.rowSize).fill(this.rowSize).map((t,e)=>Math.round((e+1)/t*100))}set hass(t){this._hass=t,this.error=null,this.entityValues=this.entities.filter(e=>(function(t,e){if(t.when){const{state:i,entity:s=t.entity,attributes:n}="string"==typeof t.when?{state:t.when}:t.when,r=e[s];return!(void 0!==i&&!ot(i,r.state))&&Object.entries(n||{}).every(([t,e])=>ot(e,r.attributes[t]))}return!0})(e,t.states)).map(t=>this.parseEntity(t))}parseEntity(t){const e=this._hass;if(!e.states.hasOwnProperty(t.entity))return this.error=`Can't find entity ${t.entity}`,t;const i=e.states[t.entity],s=i.attributes,n={name:s.friendly_name,state:i.state,value:st(i,t.attribute),unit:s.unit_of_measurement,attributes:s,domain:t.entity.split(".")[0]},r={};return t.map_state&&i.state in t.map_state&&(r.value=t.map_state[i.state]),{...n,...t,...r}}grid(t=1){("full"===t||t>this.rowSize)&&(t=this.rowSize);const e=this.gridSizes[t-1];return`flex: 0 0 ${e}%; width: ${e}%;`}_service(t,e,i){return()=>this._hass.callService(t,e,{entity_id:i})}render(){return this.error?(t=this.config.heading,e=this.error,E`
    <ha-card class="not-found">
      <h2 class="heading">
        ${t}
      </h2>
      <div class="overlay-strip">
        <div class="error">${e}</div>
      </div>
    </ha-card>
  `):E`
      <ha-card style="background: ${this.config.background};">
        ${this.renderHeading()} ${this.renderEntities()}
      </ha-card>
    `;var t,e}renderHeading(){if(!1===this.config.heading)return null;return E`
      <h2 class="heading" @click=${()=>this.config.link&&this.navigate(this.config.link)}>
        ${this.config.heading}
      </h2>
    `}renderEntities(){return 0===this.entityValues.length?null:E`
      <div class="overlay-strip">
        <div class="entities">
          ${this.entityValues.map(t=>{const e={...t,onClick:()=>this.openEntityPopover(t.entity)};if(t.action)return this.renderCustom({...e,action:()=>{const{service:e,...i}=t.action,[s,n]=e.split(".");this._hass.callService(s,n,{entity_id:t.entity,...i})}});if(!t.attribute)switch(t.domain){case"light":return this.renderDomainLight(e);case"switch":return this.renderDomainSwitch(e);case"cover":return this.renderDomainCover(e);case"media_player":return this.renderDomainMediaPlayer(e)}return this.renderDomainDefault(e)})}
        </div>
      </div>
    `}renderDomainDefault({value:t,unit:e,image:i,icon:s,name:n,size:r,onClick:o}){let a;return a=s||lt(t)?E`
        <ha-icon icon="${s||t}"></ha-icon>
      `:!0===i?E`
        <state-badge style="background-image: url(${t});"></state-badge>
      `:E`
        ${t} ${e}
      `,E`
      <div class="entity-state" style="${this.grid(r)}" @click=${o}>
        <span class="entity-name">${n}</span>
        <span class="entity-value">${a}</span>
      </div>
    `}renderCustom({value:t,unit:e,action:i,image:s,icon:n,name:r,size:o,onClick:a}){let l;return l=n||lt(t)?E`
        <paper-icon-button
          icon="${n||t}"
          role="button"
          @click=${i}
        ></paper-icon-button>
      `:!0===s?E`
        <state-badge @click=${i} style="background-image: url(${t});">
        </state-badge>
      `:E`
        <mwc-button ?dense=${!0} @click=${i}>
          ${t} ${e}
        </mwc-button>
      `,E`
      <div class="entity-state" style="${this.grid(o)}">
        <span class="entity-name" @click=${a}>${r}</span>
        <span class="entity-value">${l}</span>
      </div>
    `}renderDomainMediaPlayer({onClick:t,attributes:e,size:i,name:s,state:n,entity:r,domain:o}){const a="playing"===n,l=a?"media_pause":"media_play",c=[e.media_artist,e.media_title].join(" – ");return E`
      <div class="entity-state" style="${this.grid(i||"full")}">
        <span class="entity-name" @click=${t}>${s}</span>
        <div class="entity-value">
          <div class="entity-state-left media-title">
            ${c}
          </div>
          <div class="entity-state-right media-controls">
            <paper-icon-button
              icon="mdi:skip-previous"
              role="button"
              @click=${this._service(o,"media_previous_track",r)}
            ></paper-icon-button>
            <paper-icon-button
              icon="${a?"mdi:stop":"mdi:play"}"
              role="button"
              @click=${this._service(o,l,r)}
            ></paper-icon-button>
            <paper-icon-button
              icon="mdi:skip-next"
              role="button"
              @click=${this._service(o,"media_next_track",r)}
            ></paper-icon-button>
          </div>
        </div>
      </div>
    `}renderDomainLight({onClick:t,size:e,name:i,state:s,entity:n}){return E`
      <div class="entity-state" style="${this.grid(e)}">
        <span class="entity-name" @click=${t}>${i}</span>
        <span class="entity-value">
          <paper-toggle-button
            class="toggle"
            ?checked=${"on"===s}
            @click=${this._service("light","toggle",n)}
          />
        </span>
      </div>
    `}renderDomainSwitch({onClick:t,size:e,name:i,state:s,entity:n}){return E`
      <div class="entity-state" style="${this.grid(e)}">
        <span class="entity-name" @click=${t}>${i}</span>
        <span class="entity-value">
          <paper-toggle-button
            class="toggle"
            ?checked=${"on"===s}
            @click=${this._service("switch","toggle",n)}
          >
          </paper-toggle-button>
        </span>
      </div>
    `}renderDomainCover({onClick:t,size:e,name:i,state:s,entity:n}){const r="closed"===s;return E`
      <div class="entity-state" style="${this.grid(e)}">
        <span class="entity-name" @click=${t}>${i}</span>
        <span class="entity-value">
          <paper-icon-button
            ?disabled=${!r}
            icon="hass:arrow-up"
            role="button"
            @click=${this._service("cover","open_cover",n)}
          ></paper-icon-button>
          <paper-icon-button
            icon="hass:stop"
            role="button"
            @click=${this._service("cover","stop_cover",n)}
          ></paper-icon-button>
          <paper-icon-button
            ?disabled=${r}
            icon="hass:arrow-down"
            role="button"
            @click=${this._service("cover","close_cover",n)}
          ></paper-icon-button>
        </span>
      </div>
    `}getCardSize(){return 3}navigate(t){history.pushState(null,"",t),this.fire("location-changed",{replace:!0})}openEntityPopover(t){this.fire("hass-more-info",{entityId:t})}fire(t,e,i){i=i||{},e=null==e?{}:e;const s=new Event(t,{bubbles:void 0===i.bubbles||i.bubbles,cancelable:Boolean(i.cancelable),composed:void 0===i.composed||i.composed});return s.detail=e,this.dispatchEvent(s),s}}return window.customElements.define("banner-card",ct),ct});
