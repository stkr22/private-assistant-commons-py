## v3.2.0 (2025-07-22)

### Feat

- enhance MQTT error handling and task lifecycle management

## [6.2.0](https://github.com/stkr22/private-assistant-commons-py/compare/v6.1.0...v6.2.0) (2026-01-29)


### Features

* :card_file_box: add help_text and intent tracking to skill registration ([feafa32](https://github.com/stkr22/private-assistant-commons-py/commit/feafa32c33c236bca1c3b53bcb3b4ccdb22ff2fc))
* :card_file_box: add regex support to keywords and remove hints table ([c9e4a65](https://github.com/stkr22/private-assistant-commons-py/commit/c9e4a65c3c8317bb6d3893c333ed74ed306e55bc))
* :card_file_box: add regex support to keywords and remove hints table ([68ae4ea](https://github.com/stkr22/private-assistant-commons-py/commit/68ae4ea4e61a623644d9ccccb4b709549d1fc1d0))


### Documentation

* :card_file_box: add PostgreSQL migration scripts for skill help text and intent tracking ([9c18cc0](https://github.com/stkr22/private-assistant-commons-py/commit/9c18cc02f024ea40b9bfa2eb4ef9b0eca4b0c6b3))

## [6.1.0](https://github.com/stkr22/private-assistant-commons-py/compare/v6.0.0...v6.1.0) (2026-01-28)


### Features

* :card_file_box: add intent pattern database models and split database into domain-specific modules ([4ab56fc](https://github.com/stkr22/private-assistant-commons-py/commit/4ab56fc470f4dfe42125794fa7fe10527553fe9f))
* :card_file_box: add intent pattern database models and split database into domain-specific modules ([fba196e](https://github.com/stkr22/private-assistant-commons-py/commit/fba196ef417cd82954db48d98b542fd68e087055))

## [6.0.0](https://github.com/stkr22/private-assistant-commons-py/compare/v5.5.0...v6.0.0) (2026-01-28)


### ⚠ BREAKING CHANGES

* Removed QUERY_STATUS, QUERY_LIST, QUERY_TIME, SYSTEM_HELP, SYSTEM_REFRESH intents Added DEVICE_QUERY, MEDIA_QUERY, DATA_QUERY intents

### Code Refactoring

* :recycle: replace generic query with domain-specific query intents ([043b45a](https://github.com/stkr22/private-assistant-commons-py/commit/043b45a57e1c1b20f7b4362a0c49d6ebbbe2959b))

## [5.5.0](https://github.com/stkr22/private-assistant-commons-py/compare/v5.4.0...v5.5.0) (2026-01-05)


### Features

* :sparkles: add device duplicate checking and document MQTT retry logic [AI] ([51a121a](https://github.com/stkr22/private-assistant-commons-py/commit/51a121a1d84ce05d36dbc3f057c35ee8066091b2))


### Bug Fixes

* **deps:** update minor updates ([68b2e96](https://github.com/stkr22/private-assistant-commons-py/commit/68b2e966babc363d57f3a0945f433130fbf70a92))
* **deps:** update minor updates ([9151b5a](https://github.com/stkr22/private-assistant-commons-py/commit/9151b5a3f6fb301fbe9935d178fc5baf92eb14f5))

## [5.4.0](https://github.com/stkr22/private-assistant-commons-py/compare/v5.3.0...v5.4.0) (2026-01-01)


### Features

* :sparkles: streamline config with MqttConfig and PostgresDsn [AI] ([aa86b57](https://github.com/stkr22/private-assistant-commons-py/commit/aa86b5789c70bd01ae399705ccd449e01dcf974b))
* :sparkles: streamline config with MqttConfig and PostgresDsn [AI] ([3892b83](https://github.com/stkr22/private-assistant-commons-py/commit/3892b830e2f0d9ae61f62c9b1810376699636a69))


### Bug Fixes

* **deps:** update dependency rich to v14 ([67a6eae](https://github.com/stkr22/private-assistant-commons-py/commit/67a6eae40fb8797b38150ab16cf9a0c9faede2dd))
* **deps:** update dependency rich to v14 ([3a2c774](https://github.com/stkr22/private-assistant-commons-py/commit/3a2c774eda89b6acaac033c8d7aafd29fe70d88c))

## [5.3.0](https://github.com/stkr22/private-assistant-commons-py/compare/v5.2.2...v5.3.0) (2025-12-18)


### Features

* :sparkles: add create_skill_engine helper for resilient DB connections [AI] ([cd2b90c](https://github.com/stkr22/private-assistant-commons-py/commit/cd2b90cf903445e9accf2ddeaa1bd7f8d325a33b))
* :sparkles: add create_skill_engine helper for resilient DB connections [AI] ([20c2595](https://github.com/stkr22/private-assistant-commons-py/commit/20c2595c873d8174cf1c7330f454f999f3e69173))


### Bug Fixes

* **deps:** update dependency asyncpg to ~=0.31.0 ([254901d](https://github.com/stkr22/private-assistant-commons-py/commit/254901dc6d57f3e09a3d2b0a552194b65799c7b2))
* **deps:** update dependency asyncpg to ~=0.31.0 ([b7737c7](https://github.com/stkr22/private-assistant-commons-py/commit/b7737c70b842f5048c205003485b87eff98601be))

## [5.2.2](https://github.com/stkr22/private-assistant-commons-py/compare/v5.2.1...v5.2.2) (2025-10-20)


### Bug Fixes

* :bug: eliminate competing MQTT message loops [AI] ([905733a](https://github.com/stkr22/private-assistant-commons-py/commit/905733ab87c7d1ca15805ce218b281d9043dcdae))
* :bug: eliminate competing MQTT message loops [AI] ([124a136](https://github.com/stkr22/private-assistant-commons-py/commit/124a1363918a76d8be4349cca3cd29869b110bc9)), closes [#93](https://github.com/stkr22/private-assistant-commons-py/issues/93)

## [5.2.1](https://github.com/stkr22/private-assistant-commons-py/compare/v5.2.0...v5.2.1) (2025-10-18)


### Bug Fixes

* update relationship type hints in GlobalDevice model ([dbdc54a](https://github.com/stkr22/private-assistant-commons-py/commit/dbdc54aa3276fb4abb23cc80404157dc8c17e355))

## [5.2.0](https://github.com/stkr22/private-assistant-commons-py/compare/v5.1.0...v5.2.0) (2025-10-18)


### Features

* :sparkles: add eager loading to get_skill_devices() ([d975de3](https://github.com/stkr22/private-assistant-commons-py/commit/d975de309a753d1358367d9c5a14a47486a9a66b))
* :sparkles: add eager loading to get_skill_devices() ([f64588d](https://github.com/stkr22/private-assistant-commons-py/commit/f64588dc4fdec325960f0e118295ab29f6054b30))

## [5.1.0](https://github.com/stkr22/private-assistant-commons-py/compare/v5.0.0...v5.1.0) (2025-10-18)


### Features

* :sparkles: add SQLModel Relationship fields to database models ([75eb892](https://github.com/stkr22/private-assistant-commons-py/commit/75eb8929c0b51780a2a4ce27123b4ad89f003747))
* :sparkles: add SQLModel Relationship fields to database models ([22ee08e](https://github.com/stkr22/private-assistant-commons-py/commit/22ee08ece4ca643c7958123499f818a30b298a44))

## [5.0.0](https://github.com/stkr22/private-assistant-commons-py/compare/v4.4.0...v5.0.0) (2025-10-17)


### ⚠ BREAKING CHANGES

* skill_preparations() now auto-registers skill, must call super()

### Documentation

* 📝 update documentation for mandatory database and device registry ([d54fab2](https://github.com/stkr22/private-assistant-commons-py/commit/d54fab2e25982af3476114c33aa8a27649f7ac8e))


### Code Refactoring

* ♻️ merge device registry into BaseSkill and add device update listener ([252a0c7](https://github.com/stkr22/private-assistant-commons-py/commit/252a0c7f350166104828da146a83ddf89285cd7a))

## [4.4.0](https://github.com/stkr22/private-assistant-commons-py/compare/v4.3.1...v4.4.0) (2025-10-06)


### Features

* ✨ add device registry mixin with optional database dependencies [AI] ([a6c3024](https://github.com/stkr22/private-assistant-commons-py/commit/a6c302470f158940366e9b1f8fddfe2a69e26e48))
* ✨ add device registry mixin with optional database dependencies [AI] ([ed83033](https://github.com/stkr22/private-assistant-commons-py/commit/ed83033fe8ee719d67785ddead3cd57d7de35a6a)), closes [#81](https://github.com/stkr22/private-assistant-commons-py/issues/81)

## [4.3.1](https://github.com/stkr22/private-assistant-commons-py/compare/v4.3.0...v4.3.1) (2025-10-05)


### Miscellaneous Chores

* force release ([1b37d66](https://github.com/stkr22/private-assistant-commons-py/commit/1b37d66d683985bb0f152ff74b9e290b5db91316))

## [4.3.0](https://github.com/stkr22/private-assistant-commons-py/compare/v4.2.0...v4.3.0) (2025-10-05)


### Features

* ✨ add database models for global device registry ([cfdc15e](https://github.com/stkr22/private-assistant-commons-py/commit/cfdc15e23bfa9fc43e68c9d9ee7f8da9938dfd34))
* ✨ add database models for global device registry ([c75227b](https://github.com/stkr22/private-assistant-commons-py/commit/c75227b1db377f95db5d998258b465bcadae6b6d)), closes [#76](https://github.com/stkr22/private-assistant-commons-py/issues/76)

## [4.2.0](https://github.com/stkr22/private-assistant-commons-py/compare/v4.1.0...v4.2.0) (2025-10-04)


### Features

* ✨ merge DEVICE_TYPE into DEVICE entity with metadata ([fd3ff4a](https://github.com/stkr22/private-assistant-commons-py/commit/fd3ff4a27d416d1b77f079811b00560a3e2c3f95)), closes [#73](https://github.com/stkr22/private-assistant-commons-py/issues/73)
* ✨ merge DEVICE_TYPE into DEVICE entity with metadata ([6d2b496](https://github.com/stkr22/private-assistant-commons-py/commit/6d2b4964fc6abd4500843ed5c8047fe3ad583ca4)), closes [#73](https://github.com/stkr22/private-assistant-commons-py/issues/73)

## [4.1.0](https://github.com/stkr22/private-assistant-commons-py/compare/v4.0.0...v4.1.0) (2025-10-03)


### Features

* ✨ add RecentAction model and flexible SkillContext API ([da4f067](https://github.com/stkr22/private-assistant-commons-py/commit/da4f06765187c5feafe0401db3d398d68f68cf40))

## [4.0.0](https://github.com/stkr22/private-assistant-commons-py/compare/v3.6.0...v4.0.0) (2025-09-30)


### ⚠ BREAKING CHANGES

* Replaces IntentAnalysisResult with IntentRequest throughout the system

### Features

* ✨ add intent classification data models for structured intent processing ([321394b](https://github.com/stkr22/private-assistant-commons-py/commit/321394bc450afc56ce5bb374689015095d55348b))
* Add intent classification data models ([65e4eb6](https://github.com/stkr22/private-assistant-commons-py/commit/65e4eb6dd994d9224288730f3fe7d12dc2606a88))


### Bug Fixes

* :rotating_light: replace magic values with constants in tests to fix linting errors [AI] ([80feca2](https://github.com/stkr22/private-assistant-commons-py/commit/80feca2ce47e25da5c7d0e66be77d109e81baf2d))


### Documentation

* 📝 update documentation for intent classification models ([7e13af5](https://github.com/stkr22/private-assistant-commons-py/commit/7e13af5db377d8d3703749cf5ce19fb9b3964bb3))

## [3.6.0](https://github.com/stkr22/private-assistant-commons-py/compare/v3.5.0...v3.6.0) (2025-07-24)


### Features

* implement comprehensive testing and metrics for Issues [#48](https://github.com/stkr22/private-assistant-commons-py/issues/48), [#49](https://github.com/stkr22/private-assistant-commons-py/issues/49) ([14a56ec](https://github.com/stkr22/private-assistant-commons-py/commit/14a56ec9e579122290159eade34ac2f199a8d13f))
* Phase 3 - Testing & Monitoring (Issues [#48](https://github.com/stkr22/private-assistant-commons-py/issues/48), [#49](https://github.com/stkr22/private-assistant-commons-py/issues/49)) ([244689c](https://github.com/stkr22/private-assistant-commons-py/commit/244689c6209f39509ba0685900649b9ba91ef45a))


### Bug Fixes

* resolve linting and type issues, add metrics documentation ([626db48](https://github.com/stkr22/private-assistant-commons-py/commit/626db48c1d7353cefcd30e39c91505d77e035a62))

## [3.5.0](https://github.com/stkr22/private-assistant-commons-py/compare/v3.4.0...v3.5.0) (2025-07-24)


### Features

* enhance documentation and type hints across all modules ([f70c44c](https://github.com/stkr22/private-assistant-commons-py/commit/f70c44c765f7c81e8c6fb7cfeba0290ea9456b24))
* enhance documentation and type hints across all modules ([d1af24d](https://github.com/stkr22/private-assistant-commons-py/commit/d1af24dfc4d11d1bdde58108b87a35f21beba02c))

## [3.4.0](https://github.com/stkr22/private-assistant-commons-py/compare/v3.3.0...v3.4.0) (2025-07-24)


### Features

* enhance skill_logger with rich console and visual improvements ([ee87e5c](https://github.com/stkr22/private-assistant-commons-py/commit/ee87e5ca7f80a250ee6d1b26512eaf50f3f4a462))
* enhance skill_logger with rich console and visual improvements ([8261214](https://github.com/stkr22/private-assistant-commons-py/commit/8261214be9ae355c35b2f852d0819298ad3f8305))

## [3.3.0](https://github.com/stkr22/private-assistant-commons-py/compare/v3.2.0...v3.3.0) (2025-07-23)


### Features

* add Python version matrix testing and update supported versions ([8ea1a41](https://github.com/stkr22/private-assistant-commons-py/commit/8ea1a41f8ee67bc3130c138a9b5ede9ea2229cf3))
* add Python version matrix testing and update supported versions [AI] ([11d57bc](https://github.com/stkr22/private-assistant-commons-py/commit/11d57bc8711810050e78d99c403697c47a90e6e7))
* enhance MQTT error handling and task lifecycle management ([299bdbf](https://github.com/stkr22/private-assistant-commons-py/commit/299bdbf7e741be30ce1ccb26c7d99226a15c499c))

## v3.1.0 (2025-07-22)

### Feat

- implement performance and concurrency improvements

## v3.0.2 (2025-07-20)

### Fix

- failing test update uv workflow version
- failing tests
- :rotating_light: removed outdated type declaration
- **deps**: update dependency aiomqtt to ~=2.4.0

## v3.0.0 (2024-12-25)

### BREAKING CHANGE

- Removing AsyncTyper
fixes #12

### Refactor

- :fire: Removing async typer custom implementation using alternative implementation in skills
- :recycle: Updating copier template, migrating to uv

## v2.1.0 (2024-11-30)

### Feat

- :sparkles: Allowing skill prepartions to be executed

## v2.0.0 (2024-11-24)

### BREAKING CHANGE

- Renamed publish methods and made response an object;

### Feat

- Implement structure response and alert responses Fixes #9

## v1.1.2 (2024-11-13)

## v1.1.1 (2024-11-10)

## v1.1.0 (2024-10-03)

## v1.0.3 (2024-10-03)

## v1.0.2 (2024-10-03)

## v1.0.1 (2024-10-03)

## v1.0.0 (2024-10-03)

## v0.1.6 (2024-08-16)

## v0.1.5 (2024-08-16)

### Feat

- Refactor BaseSkill class, enhance unit tests, and implement centralized logging

## v0.1.4 (2024-08-04)

## v0.1.3 (2024-07-16)

## v0.1.2 (2024-07-14)

## v0.1.1 (2024-04-16)

## v0.1.0 (2024-04-15)
