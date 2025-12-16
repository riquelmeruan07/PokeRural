from settings import * 
from sprites import MonsterSprite, MonsterNameSprite, MonsterLevelSprite, MonsterStatsSprite, MonsterOutlineSprite, AttackSprite, TimedSprite
from groups import BattleSprites
from game_data import ATTACK_DATA
from support import draw_bar
from tempo import Tempo
from random import choice

class Battle:
	# main
	def __init__(self, player_monsters, opponent_monsters, monster_frames, bg_surf, fonts, end_battle, character, sounds):
		# general
		self.display_surface = pygame.display.get_surface()
		self.bg_surf = bg_surf
		self.monster_frames = monster_frames
		self.fonts = fonts
		
		self.cursor_surf = pygame.Surface((20, 20), pygame.SRCALPHA)
		pygame.draw.polygon(self.cursor_surf, (255, 255, 0), [(10, 0), (0, 20), (20, 20)])

		self.monster_data = {'player': player_monsters, 'opponent': opponent_monsters}
		self.battle_over = False
		self.end_battle = end_battle
		self.character = character
		self.sounds = sounds

		# timers 
		self.timers = {
			'opponent delay': Tempo(600, func = self.opponent_attack)
		}

		# groups
		self.battle_sprites   = BattleSprites()
		self.player_sprites   = pygame.sprite.Group()
		self.opponent_sprites = pygame.sprite.Group()
  
		self.selecting_attacker = True
		self.player_attacker_index = 0
		self.selected_attacker = None

		# control
		self.current_monster = None
		self.selection_mode  = None
		self.selected_attack = None
		self.selection_side  = 'player'
		self.indexes = {
			'general': 0,
			'monster': 0,
			'attacks': 0,
			'switch' : 0,
			'target' : 0,
			'choose_attacker': 0,
		}

		self.setup()

	def setup(self):
		for entity, monster in self.monster_data.items():
			for index, monster in {k:v for k,v in monster.items() if k <= 2}.items():
				self.create_monster(monster, index, index, entity)

			# remove opponent monster data 
			for i in range(len(self.opponent_sprites)):
				del self.monster_data['opponent'][i]

	def create_monster(self, monster, index, pos_index, entity):
		monster.paused = False
		
		monster_key = monster.name.strip().lower()
		
		monster_data = self.monster_frames['monsters'][monster_key] 
		
		frames = monster_data 
		
		if 'outlines' in monster_data:
			outline_frames = monster_data['outlines']
		else:
			# Agora 'frames' está definido e pode ser usado para o fallback.
			outline_frames = frames 
			print(f"Aviso: Monstro '{monster_key}' não possui a chave 'outlines'. Usando frames normais.")
			
		
		if entity == 'player':
			pos = list(BATTLE_POSITIONS['left'].values())[pos_index]
			groups = (self.battle_sprites, self.player_sprites)
			
			# O flip é aplicado nos dicionários de estado (frames e outline_frames)
			frames = {state: [pygame.transform.flip(frame, True, False) for frame in frames_list] for state, frames_list in frames.items()}
			outline_frames = {state: [pygame.transform.flip(frame, True, False) for frame in frames_list] for state, frames_list in outline_frames.items()}
		else:
			pos = list(BATTLE_POSITIONS['right'].values())[pos_index]
			groups = (self.battle_sprites, self.opponent_sprites)

		monster_sprite = MonsterSprite(pos, frames, groups, monster, index, pos_index, entity, self.apply_attack, self.create_monster)
		MonsterOutlineSprite(monster_sprite, self.battle_sprites, outline_frames)

		# ui
		name_pos = monster_sprite.rect.midleft + vector(16,-70) if entity == 'player' else monster_sprite.rect.midright + vector(-40,-70)
		name_sprite = MonsterNameSprite(name_pos, monster_sprite, self.battle_sprites, self.fonts['regular'])
		level_pos = name_sprite.rect.bottomleft if entity == 'player' else name_sprite.rect.bottomright 
		MonsterLevelSprite(entity, level_pos, monster_sprite, self.battle_sprites, self.fonts['small'])
		MonsterStatsSprite(monster_sprite.rect.midbottom + vector(0,20), monster_sprite, (150,48), self.battle_sprites, self.fonts['small'])
  
	def input(self):
		if self.selection_mode and self.current_monster:
			keys = pygame.key.get_just_pressed()

			# Limites para cada menu
			match self.selection_mode:
				case 'general':         limiter = len(BATTLE_CHOICES['full'])
				case 'choose_attacker': limiter = len(self.player_sprites)
				case 'attacks':         limiter = len(self.current_monster.monster.get_abilities(all=False))
				case 'switch':          limiter = len(self.available_monsters)
				case 'target':
					limiter = len(self.opponent_sprites) if self.selection_side == 'opponent' \
						else len(self.player_sprites)

			# Navegação
			if keys[pygame.K_DOWN]:
				self.indexes[self.selection_mode] = (self.indexes[self.selection_mode] + 1) % limiter
			if keys[pygame.K_UP]:
				self.indexes[self.selection_mode] = (self.indexes[self.selection_mode] - 1) % limiter

			# CONFIRMAR ESCOLHA --------------------------------------
			if keys[pygame.K_SPACE]:

				# ---------------------------------------------
				# 1. TROCA (switch)
				# ---------------------------------------------
				if self.selection_mode == 'switch':
					switch_list = list(self.available_monsters.items())
					if not switch_list:
						self.selection_mode = "general"
						return

					if self.indexes['switch'] >= len(switch_list):
						self.indexes['switch'] = len(switch_list) - 1

					index, new_monster = switch_list[self.indexes['switch']]

					old_pos = self.current_monster.pos_index
					self.current_monster.kill()
					self.create_monster(new_monster, index, old_pos, 'player')

					self.selection_mode = None
					self.update_all_monsters('resume')

				# ---------------------------------------------
				# 2. ALVO (target)
				# ---------------------------------------------
				if self.selection_mode == 'target':
					sprite_group = self.opponent_sprites if self.selection_side == 'opponent' else self.player_sprites
					sprite_list = sprite_group.sprites()

					if self.indexes['target'] >= len(sprite_list):
						self.indexes['target'] = len(sprite_list) - 1

					target_sprite = sprite_list[self.indexes['target']]

					# Ataque
					if self.selected_attack:
						self.current_monster.activate_attack(target_sprite, self.selected_attack)
						self.selected_attack = None
						self.current_monster = None
						self.selection_mode = None
						return

					# Captura (se não for ataque)
					if target_sprite.monster.health < target_sprite.monster.get_stat('max_health') * 0.9:
						self.monster_data['player'][len(self.monster_data['player'])] = target_sprite.monster
						target_sprite.delayed_kill(None)
						self.update_all_monsters('resume')
					else:
						TimedSprite(target_sprite.rect.center, self.monster_frames['ui']['cross'], self.battle_sprites, 1000)

				# ---------------------------------------------
				# 3. ESCOLHER HABILIDADE (attacks)
				# ---------------------------------------------
				if self.selection_mode == 'attacks':
					self.selection_mode = 'target'
					self.indexes['target'] = 0
					self.selected_attack = self.current_monster.monster.get_abilities(all=False)[self.indexes['attacks']]
					self.selection_side = ATTACK_DATA[self.selected_attack]['target']
					return

				# ---------------------------------------------
				# 4. MENU GERAL
				# ---------------------------------------------
				if self.selection_mode == 'general':
					# OPC 0 — ATACAR → escolher atacante
					if self.indexes['general'] == 0:
						self.selection_mode = 'choose_attacker'
						self.indexes['choose_attacker'] = 0
						return

					# OPC 1 — Defender
					if self.indexes['general'] == 1:
						self.current_monster.monster.defending = True
						self.update_all_monsters('resume')
						self.current_monster = None
						self.selection_mode = None
						return

					# OPC 2 — Trocar
					if self.indexes['general'] == 2:
						self.selection_mode = 'switch'
						return

					# OPC 3 — Escolher alvo direto
					if self.indexes['general'] == 3:
						self.selection_mode = 'target'
						self.selection_side = 'opponent'
						return

				# ---------------------------------------------
				# 5. ESCOLHER QUAL MONSTRO VAI ATACAR
				# ---------------------------------------------
				if self.selection_mode == 'choose_attacker':
					sprite_list = self.player_sprites.sprites()

					if self.indexes['choose_attacker'] >= len(sprite_list):
						self.indexes['choose_attacker'] = len(sprite_list) - 1

					# Define atacante
					attacker_sprite = sprite_list[self.indexes['choose_attacker']]
					self.current_monster = attacker_sprite

					self.selection_mode = "attacks"
					self.indexes['attacks'] = 0
					return

	def update_timers(self):
		for timer in self.timers.values():
			timer.update()

	def normalize_indexes(self):
    
		p_list = self.player_sprites.sprites()
		max_p = max(0, len(p_list) - 1)

		if 'choose_attacker' in self.indexes:
			self.indexes['choose_attacker'] = min(self.indexes['choose_attacker'], max_p)

		if 'general' in self.indexes:
			self.indexes['general'] = min(self.indexes['general'], len(BATTLE_CHOICES['full']) - 1)

		# OPONENTE
		o_list = self.opponent_sprites.sprites()
		max_o = max(0, len(o_list) - 1)

		if 'target' in self.indexes:
			self.indexes['target'] = min(self.indexes['target'], max_o)

		# SELEÇÃO DE ATAQUES
		if self.current_monster:
			abilities = self.current_monster.monster.get_abilities(all=False)
			if abilities:
				self.indexes['attacks'] = min(self.indexes['attacks'], len(abilities) - 1)
			else:
				self.indexes['attacks'] = 0

	def ensure_attacker_is_valid(self):
		sprites = self.player_sprites.sprites()
		if not sprites:
			return

		idx = self.indexes['choose_attacker']
		idx = min(idx, len(sprites) - 1)
		
		self.current_monster = sprites[idx]

	# battle system
	def check_active(self):
		for monster_sprite in self.player_sprites.sprites() + self.opponent_sprites.sprites():
			if monster_sprite.monster.initiative >= 100:
				monster_sprite.monster.defending = False
				self.update_all_monsters('pause')
				monster_sprite.monster.initiative = 0
				monster_sprite.set_highlight(True)
				self.current_monster = monster_sprite
				if monster_sprite.entity == 'player':
					self.selection_mode = 'general'
				else:
					self.timers['opponent delay'].activate()

	def update_all_monsters(self, option):
		for monster_sprite in self.player_sprites.sprites() + self.opponent_sprites.sprites():
			monster_sprite.monster.paused = True if option == 'pause' else False

	def apply_attack(self, target_sprite, attack, amount):
		AttackSprite(target_sprite.rect.center, self.monster_frames['attacks'][ATTACK_DATA[attack]['animation']], self.battle_sprites)
		self.sounds[ATTACK_DATA[attack]['animation']].play()

		# get correct attack damage amount (defense, element)
		attack_element = ATTACK_DATA[attack]['element']
		target_element = target_sprite.monster.element

		# double attack
		if attack_element == 'fire'  and target_element == 'plant' or \
		   attack_element == 'water' and target_element == 'fire'  or \
		   attack_element == 'plant' and target_element == 'water':
			amount *= 2

		# halve attack
		if attack_element == 'fire'  and target_element == 'water' or \
		   attack_element == 'water' and target_element == 'plant' or \
		   attack_element == 'plant' and target_element == 'fire':
			amount *= 0.5

		target_defense = 1 - target_sprite.monster.get_stat('defense') / 2000
		if target_sprite.monster.defending:
			target_defense -= 0.2
		target_defense = max(0, min(1, target_defense))

		# update the monster health 
		target_sprite.monster.health -= amount * target_defense
		self.check_death()

		# resume 
		self.update_all_monsters('resume')

	def check_death(self):
		dead_sprites = []

		for monster_sprite in self.player_sprites.sprites() + self.opponent_sprites.sprites():
			if monster_sprite.monster.health <= 0:
				dead_sprites.append(monster_sprite)

		if not dead_sprites:
			return

		for monster_sprite in dead_sprites:

			# se o monstro morto era o monstro atual → limpar antes de remover o sprite
			if monster_sprite == self.current_monster:
				self.current_monster = None
				self.selection_mode = None

			# PLAYER MORREU
			if monster_sprite.entity == 'player':
				active = [(s.index, s.monster) for s in self.player_sprites.sprites()]
				available = [
					(index, monster) 
					for index, monster in self.monster_data['player'].items()
					if monster.health > 0 and (index, monster) not in active
				]

				if available:
					new_monster_data = (available[0][1], available[0][0], monster_sprite.pos_index, 'player')
				else:
					new_monster_data = None
			
			# OPONENTE MORREU
			else:
				if self.monster_data['opponent']:
					# próximo monstro
					next_index = sorted(self.monster_data['opponent'])[0]
					new_monster_data = (
						self.monster_data['opponent'][next_index],
						monster_sprite.index,
						monster_sprite.pos_index,
						'opponent'
					)
					del self.monster_data['opponent'][next_index]
				else:
					new_monster_data = None

				# XP
				xp_amount = monster_sprite.monster.level * 100 / max(1, len(self.player_sprites))
				for player_sprite in self.player_sprites:
					player_sprite.monster.update_xp(xp_amount)

			# remover sprite morto
			monster_sprite.delayed_kill(new_monster_data)

		# 2 - Ajustar índices após a morte
		self.normalize_indexes()
		self.ensure_attacker_is_valid()

	def opponent_attack(self):
		ability = choice(self.current_monster.monster.get_abilities())
		random_target = choice(self.opponent_sprites.sprites()) if ATTACK_DATA[ability]['target'] == 'player' else choice(self.player_sprites.sprites())
		self.current_monster.activate_attack(random_target, ability)

	def check_end_battle(self):
		# opponents have been defeated 
		if len(self.opponent_sprites) == 0 and not self.battle_over:
			self.battle_over = True
			self.end_battle(self.character)
			for monster in self. monster_data['player'].values():
				monster.initiative = 0

		# player has been defeated 
		if len(self.player_sprites) == 0:
			pygame.quit()
			exit()

	def draw_target_cursor(self):
    # grupo do alvo
		sprite_group = self.opponent_sprites if self.selection_side == 'opponent' else self.player_sprites
		sprite_list = sprite_group.sprites()

		if not sprite_list:
			return
		
		# proteger índice
		if self.indexes['target'] >= len(sprite_list):
			self.indexes['target'] = len(sprite_list) - 1

		target_sprite = sprite_list[self.indexes['target']]

		# posição do cursor acima do monstro
		cursor_rect = self.cursor_surf.get_frect(
			center = (target_sprite.rect.centerx, target_sprite.rect.top - 25)
		)

		self.display_surface.blit(self.cursor_surf, cursor_rect)

	def draw_cursor(self, sprite):
		if not sprite:
			return

		x, y = sprite.rect.centerx, sprite.rect.top - 15

		points = [
			(x, y),         # ponta
			(x - 8, y + 12),
			(x + 8, y + 12)
		]

		pygame.draw.polygon(self.display_surface, (255, 255, 0), points)
    
	def draw_ui(self):

		if self.current_monster:
			if self.selection_mode == 'general':
				self.draw_general()
			if self.selection_mode == 'attacks':
				self.draw_attacks()
			if self.selection_mode == 'switch':
				self.draw_switch()

			if hasattr(self, "selection_side") and self.selection_mode == "target":
				if self.selection_side == "opponent":
					max_targets = len(self.opponent_sprites)
				else:
					max_targets = len(self.player_sprites)

				target_index = self.indexes.get("target", 0)

				if max_targets > 0:
					target_index = max(0, min(target_index, max_targets - 1))
				else:
					target_index = 0
			else:
				target_index = 0
			
			self.battle_sprites.draw(
				self.display_surface,
				self.selection_side if hasattr(self, "selection_side") else None,
				self.selection_mode,
				target_index,  # AGORA O ÍNDICE ESTÁ CORRETO
				self.player_sprites,
				self.opponent_sprites
			)

			if self.selection_mode == "choose_attacker":
				sprite_list = self.player_sprites.sprites()
				if sprite_list:
					attacker = sprite_list[self.indexes['choose_attacker']]
					self.draw_cursor(attacker)

			
			if self.selection_mode == "target":
				group = self.opponent_sprites if self.selection_side == 'opponent' else self.player_sprites
				sprite_list = group.sprites()
				if sprite_list:
					target = sprite_list[target_index]   # ← usa o índice seguro aqui também
					self.draw_cursor(target)


	def draw_general(self):
		for index, (option, data_dict) in enumerate(BATTLE_CHOICES['full'].items()):
			if index == self.indexes['general']:
				surf = self.monster_frames['ui'][f"{data_dict['icon']}_highlight"]
			else:
				surf = pygame.transform.grayscale(self.monster_frames['ui'][data_dict['icon']])
			rect = surf.get_frect(center = self.current_monster.rect.midright + data_dict['pos'])
			self.display_surface.blit(surf, rect)

	def draw_attacks(self):
		# data
		abilities = self.current_monster.monster.get_abilities(all = False)
		width, height = 150, 200
		visible_attacks = 4
		item_height = height / visible_attacks
		v_offset = 0 if self.indexes['attacks'] < visible_attacks else -(self.indexes['attacks'] - visible_attacks + 1) * item_height

		# bg
		bg_rect = pygame.FRect((0,0), (width,height)).move_to(midleft = self.current_monster.rect.midright + vector(20,0))
		pygame.draw.rect(self.display_surface, COLORS['white'], bg_rect, 0, 5)

		for index, ability in enumerate(abilities):
			selected = index == self.indexes['attacks']

			# text 
			if selected:
				element = ATTACK_DATA[ability]['element']
				text_color = COLORS[element] if element!= 'normal' else COLORS['black']
			else:
				text_color = COLORS['light']
			text_surf  = self.fonts['regular'].render(ability, False, text_color)

			# rect 
			text_rect = text_surf.get_frect(center = bg_rect.midtop + vector(0, item_height / 2 + index * item_height + v_offset))
			text_bg_rect = pygame.FRect((0,0), (width, item_height)).move_to(center = text_rect.center)

			# draw
			if bg_rect.collidepoint(text_rect.center):
				if selected:
					if text_bg_rect.collidepoint(bg_rect.topleft):
						pygame.draw.rect(self.display_surface, COLORS['dark white'], text_bg_rect,0,0,5,5)
					elif text_bg_rect.collidepoint(bg_rect.midbottom + vector(0,-1)):
						pygame.draw.rect(self.display_surface, COLORS['dark white'], text_bg_rect,0,0,0,0,5,5)
					else:
						pygame.draw.rect(self.display_surface, COLORS['dark white'], text_bg_rect)

				self.display_surface.blit(text_surf, text_rect)

	def draw_switch(self):
		# data 
		width, height = 300, 320
		visible_monsters = 4
		item_height = height / visible_monsters
		v_offset = 0 if self.indexes['switch'] < visible_monsters else -(self.indexes['switch'] - visible_monsters + 1) * item_height
		bg_rect = pygame.FRect((0,0), (width, height)).move_to(midleft = self.current_monster.rect.midright + vector(20,0))
		pygame.draw.rect(self.display_surface, COLORS['white'], bg_rect, 0, 5)

		# monsters 
		active_monsters = [(monster_sprite.index, monster_sprite.monster) for monster_sprite in self.player_sprites]
		self.available_monsters = {index: monster for index, monster in self.monster_data['player'].items() if (index, monster) not in active_monsters and monster.health > 0}

		for index, monster in enumerate(self.available_monsters.values()):
			selected = index == self.indexes['switch']
			item_bg_rect = pygame.FRect((0,0), (width, item_height)).move_to(midleft = (bg_rect.left, bg_rect.top + item_height / 2 + index * item_height + v_offset))

			icon_surf = self.monster_frames['icons'][monster.name]
			icon_rect = icon_surf.get_frect(midleft = bg_rect.topleft + vector(10,item_height / 2 + index * item_height + v_offset))
			text_surf = self.fonts['regular'].render(f'{monster.name} ({monster.level})', False, COLORS['red'] if selected else COLORS['black'])
			text_rect = text_surf.get_frect(topleft = (bg_rect.left + 90, icon_rect.top))

			# selection bg
			if selected:
				if item_bg_rect.collidepoint(bg_rect.topleft):
					pygame.draw.rect(self.display_surface, COLORS['dark white'], item_bg_rect, 0, 0, 5, 5)
				elif item_bg_rect.collidepoint(bg_rect.midbottom + vector(0,-1)):
					pygame.draw.rect(self.display_surface, COLORS['dark white'], item_bg_rect, 0, 0, 0, 0, 5, 5)
				else:
					pygame.draw.rect(self.display_surface, COLORS['dark white'], item_bg_rect)

			if bg_rect.collidepoint(item_bg_rect.center):
				for surf, rect in ((icon_surf, icon_rect), (text_surf, text_rect)):
					self.display_surface.blit(surf, rect)
				health_rect = pygame.FRect((text_rect.bottomleft + vector(0,4)), (100,4))
				energy_rect = pygame.FRect((health_rect.bottomleft + vector(0,2)), (80,4))
				draw_bar(self.display_surface, health_rect, monster.health, monster.get_stat('max_health'), COLORS['red'], COLORS['black'])
				draw_bar(self.display_surface, energy_rect, monster.energy, monster.get_stat('max_energy'), COLORS['blue'], COLORS['black'])

	def update(self, dt):
		self.check_end_battle()
		
		# updates
		self.input()
		self.update_timers()
		self.battle_sprites.update(dt)
		self.check_active()
		self.normalize_indexes()
		# drawing
		self.display_surface.blit(self.bg_surf, (0,0))
		self.battle_sprites.draw(self.current_monster, self.selection_side, self.selection_mode, self.indexes['target'], self.player_sprites, self.opponent_sprites)
		self.draw_ui()