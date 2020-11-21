import pygame
import sys
import math
import numpy as np
import random
import time
from screeninfo import get_monitors



pygame.mixer.init()
pygame.init()

monitor = get_monitors()[0]
screen_shape = (monitor.width, monitor.height)
screen = pygame.display.set_mode(screen_shape, pygame.FULLSCREEN)


class RWSprite(pygame.sprite.Sprite):
    GRAVITATIONAL_CONSTANT = 180
    MAX_GRAVITY = 20

    def __init__(self, black_hole_group):
        super().__init__()
        self.black_hole_group = black_hole_group

    def calculate_gravity(self):
        pos = self.rect.center
        vector = np.array([0., 0.])
        for black_hole in self.black_hole_group:
            relative_pos = tuple(a - b for a,b in zip(pos, black_hole.rect.center))
            angle = math.atan(relative_pos[1] / relative_pos[0]) if relative_pos[0] != 0 else math.pi / 2
            distance = math.sqrt(relative_pos[0]**2 + relative_pos[1]**2)
            vector += np.array([-self.GRAVITATIONAL_CONSTANT / math.copysign(distance**1.1, rel) if distance != 0 else 0 for rel in relative_pos])
        net_gravity = math.sqrt(vector[0]**2 + vector[1]**2)
        if net_gravity > self.MAX_GRAVITY:
            vector *= self.MAX_GRAVITY / net_gravity
        return vector


class BlackHole(pygame.sprite.Sprite):
    raw_image = pygame.image.load('assets/black_hole.png').convert()

    def __init__(self, pos, size=None):
        super().__init__()
        self.image = self.raw_image.copy()
        self.size = size
        if size is not None:
            self.image = pygame.transform.scale(self.image, (size, size))
        self.rect = self.image.get_rect(center=pos)

    @property
    def gravity(self):
        return self.size / 100

    def enlarge(self):
        if self.size <= 200:
            self.size += 3
            self.image = pygame.transform.scale(self.raw_image.copy(), (self.size, self.size))


class Fighter(RWSprite):
    directions = {'right': {'angle': 0},
                  'downright': {'angle': math.radians(45)},
                  'down': {'angle': math.radians(90)},
                  'downleft': {'angle': math.radians(135)},
                  'left': {'angle': math.radians(180)},
                  'upleft': {'angle': math.radians(225)},
                  'up': {'angle': math.radians(270)},
                  'upright': {'angle': math.radians(315)}}
    for direction in directions.keys():
        directions[direction]['image'] = pygame.image.load(f'assets/fighter_{direction}.png').convert_alpha()
    torpedo_sound = pygame.mixer.Sound('assets/torpedo.wav')
    death_image = pygame.image.load('assets/fighter-death.png')
    death_sound = pygame.mixer.Sound('assets/fighter-death.wav')
    death_time = None

    def __init__(self, screen_shape, black_hole_group, torpedo_group, sound_effects=True, pos=None):
        super().__init__(black_hole_group)
        self.black_hole_group = black_hole_group
        self.torpedo_group = torpedo_group
        self.screen_shape = screen_shape
        self.sound_effects = sound_effects
        if pos is None:
            self.initial_pos = (100, 100)
        else:
            self.initial_pos = pos
        self.velocity = [0, 0]  # speed x, speed y
        self.direction = 'right'  # degrees
        self.acceleration = 1

        self.image = self.directions[self.direction]['image']
        self.rect = self.image.get_rect(center=self.initial_pos)

    def _update_direction(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w] and keys[pygame.K_d]:
            self.direction = 'upright'
        elif keys[pygame.K_d] and keys[pygame.K_s]:
            self.direction = 'downright'
        elif keys[pygame.K_s] and keys[pygame.K_a]:
            self.direction = 'downleft'
        elif keys[pygame.K_a] and keys[pygame.K_w]:
            self.direction = 'upleft'
        elif keys[pygame.K_w]:
            self.direction = 'up'
        elif keys[pygame.K_d]:
            self.direction = 'right'
        elif keys[pygame.K_s]:
            self.direction = 'down'
        elif keys[pygame.K_a]:
            self.direction = 'left'
        
    def _move(self):
        new_center = [math.ceil(a + b) for a,b in zip(self.rect.center, self.velocity)]
        for i in range(2):
            if new_center[i] < 0:
                new_center[i] = 0
                if self.velocity[i] <= 0:
                    self.velocity[i] = 0
                self.velocity[i] = 0
            elif new_center[i] > self.screen_shape[i]:
                new_center[i] = self.screen_shape[i]
                if self.velocity[i] >= 0:
                    self.velocity[i] = 0
        self.rect.center = tuple(new_center)

    def _accelerate(self, gravity):
        DRAG = 0.05
        if self.death_time is None:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w] or keys[pygame.K_a] or keys[pygame.K_s] or keys[pygame.K_d]:
                angle = self.directions[self.direction]['angle']
                self.velocity = [math.cos(angle) * self.acceleration + self.velocity[0],
                                math.sin(angle) * self.acceleration + self.velocity[1]]
        self.velocity = [a + b for a,b in zip(self.velocity, gravity)]
        self.velocity = [v * (1 - DRAG) for v in self.velocity]

    def update(self):
        if self.death_time:
            if time.time() > self.death_time + 1:
                self.reset()
        else:
            self._update_direction()
            self.image = self.directions[self.direction]['image']
        gravity = self.calculate_gravity()
        self._accelerate(gravity)
        self._move()

    def draw(self, screen):
        screen.blit(self.image, self.rect)

    def reset(self):
        self.direction = 'right'
        self.velocity = [0, 0]
        self.rect.center = self.initial_pos
        self.death_time = None
    
    def fire(self):
        if self.death_time is None:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            init_x, init_y = self.rect.center
            delta_x = mouse_x - init_x
            delta_y = init_y - mouse_y
            angle = math.degrees(math.atan(delta_y / delta_x)) if delta_x != 0 else 0
            if delta_x < 0:
                angle += 180
            self.torpedo_group.add(Torpedo((init_x, init_y), angle, self.screen_shape, self.black_hole_group))
            if self.sound_effects:
                self.torpedo_sound.play()

    def destroy(self, angle):
        if self.death_time is None:
            self.image = pygame.transform.rotate(self.death_image.copy(), angle)
            if self.sound_effects:
                self.death_sound.play()
            self.death_time = time.time()


class Crosshair(pygame.sprite.Sprite):
    image = pygame.image.load('assets/crosshair.png').convert_alpha()
    rect = image.get_rect()

    def __init__(self):
        super().__init__()

    def update(self):
        self.rect.center = pygame.mouse.get_pos()

    def draw(self, screen):
        screen.blit(self.image, self.rect)


class Torpedo(RWSprite):
    raw_image = pygame.image.load('assets/torpedo.png').convert_alpha()

    def __init__(self, pos, angle, screen_shape, black_hole_group, speed=20):
        super().__init__(black_hole_group)
        self.image = self.raw_image.copy()
        self.speed = speed
        self.angle = angle
        velocity_x = math.cos(math.radians(angle)) * self.speed
        velocity_y = -math.sin(math.radians(angle)) * self.speed
        self.velocity = np.array([velocity_x, velocity_y])
        self.image = pygame.transform.rotate(self.image, self.angle)
        self.rect = self.image.get_rect(center=pos)
        self.screen_shape =  screen_shape
        self.black_hole_group = black_hole_group

    def update(self):
        init_angle = self.angle
        gravity = self.calculate_gravity()
        self.velocity = [a + b for a,b in zip(self.velocity, gravity)]
        self.rect.center = [math.ceil(a + b) for a,b in zip(self.rect.center, self.velocity)]
        self.angle = math.degrees(math.atan(-self.velocity[1] / self.velocity[0])) if self.velocity[0] != 0 else 90
        if self.velocity[0] < 0:
            self.angle += 180
        # self.image = pygame.transform.rotate(self.image, self.angle - init_angle)
        self.image = pygame.transform.rotate(self.raw_image.copy(), self.angle)
        if not 0 < self.rect.center[0] < self.screen_shape[0] or not 0 < self.rect.center[1] < self.screen_shape[1]:
            self.kill()
        elif pygame.sprite.spritecollide(self, self.black_hole_group, False):
            self.kill()
    
    def draw(self, screen):
        screen.blit(self.image, self.rect)


class Drone(RWSprite):
    sound_death = pygame.mixer.Sound('assets/drone-death.wav')
    death_time = None
    torpedo_sound = pygame.mixer.Sound('assets/torpedo.wav')
    image = pygame.image.load('assets/drone.png').convert_alpha()
    image_death = pygame.image.load('assets/drone-death.png').convert_alpha()

    def __init__(self, screen_shape, black_hole_group, enemy_torpedo_group, sound_effects):
        super().__init__(black_hole_group)
        self.enemy_torpedo_group = enemy_torpedo_group
        self.screen_shape = screen_shape
        self.black_hole_group = black_hole_group
        self.sound_effects = sound_effects
        speed = 8
        if random.choice([True, False]):
            pos = (random.choice([0, screen_shape[0]]), random.randrange(0, screen_shape[1]))
            self.velocity = (speed * (1 if pos[0] == 0 else -1), random.choice([-3, 3]))
        else:
            pos = (random.randrange(0, screen_shape[0]), random.choice([0, screen_shape[1]]))
            self.velocity = (random.choice([-3, 3]), speed * (1 if pos[1] == 0 else -1))
        self.rect = self.image.get_rect(center=pos)
        self.drag = 0.1
        self.init_time = time.time()
        self.last_fired_time = self.init_time

    def update(self):
        gravity = self.calculate_gravity()
        self.velocity = [(a + b) * (1 - self.drag) for a,b in zip(self.velocity, gravity)]
        self.rect.center = [math.ceil(a + b) for a,b in zip(self.rect.center, self.velocity)]
        if not 0 <= self.rect.center[0] <= self.screen_shape[0] or not 0 <= self.rect.center[1] <= self.screen_shape[1]:
            self.kill()
        elif pygame.sprite.spritecollide(self, self.black_hole_group, False):
            self.kill()
        elif time.time() > self.init_time + 10:
            self.kill()
        elif time.time() > self.last_fired_time + 1.5 and self.death_time is None:
            for angle in np.arange(0, 7) * 45:
                self.enemy_torpedo_group.add(Torpedo(self.rect.center, angle, self.screen_shape, self.black_hole_group, speed=10))
            if self.sound_effects:
                self.torpedo_sound.play()
            self.last_fired_time = time.time()
        elif self.death_time:
            if time.time() > self.death_time + 0.5:
                self.kill()

    def draw(self, screen):
        screen.blit(self.image, self.rect)

    def destroy(self, angle):
        if self.death_time is None:
            self.image = pygame.transform.rotate(self.image_death.copy(), angle)
            if self.sound_effects:
                self.sound_death.play()
            self.death_time = time.time()


class Star:
    def __init__(self, pos, color, radius):
        self.pos = pos
        self.color = color
        self.radius = radius

    def draw(self, screen):
        posint = tuple(map(int, self.pos))
        pygame.draw.circle(screen, self.color, posint, self.radius)

class Stars:
    colors = ((x, x, x) for x in (80, 120, 145, 180, 225))
    star_options = tuple(zip((1, 1, 2, 2, 3), (colors)))
    weights = (60, 30, 15, 7, 3)
    num_stars = 500
    velocity = (-.2, .1)

    def __init__(self, screen_shape):
        self.screen_shape = screen_shape
        self.init_stars()

    def update(self):
        num_new = 0
        for i in reversed(range(len(self.stars))):
            star = self.stars[i]
            # offset stars
            star.pos = tuple(p + v for p,v in zip(star.pos, self.velocity))
            # delete stars off-screen
            if not (0 < star.pos[0] < self.screen_shape[0] and 0 < star.pos[1] < self.screen_shape[1]):
                del self.stars[i]
                num_new += 1
        # gen stars
        self.new_stars(num_new)

    def new_stars(self, num_new):
        star_params = random.choices(self.star_options, weights=self.weights, k=num_new)

        axis_weights = tuple(map(abs, self.velocity))
        axes = random.choices(('x', 'y'), weights=axis_weights, k=num_new)

        for (radius, color), axis in zip(star_params, axes):
            if axis == 'x':
                pos = (
                    random.randint(0, self.screen_shape[0]),
                    0 if self.velocity[1] > 0 else self.screen_shape[1]
                )
            else:
                pos = (
                    0 if self.velocity[0] > 0 else self.screen_shape[0],
                    random.randint(0, self.screen_shape[1])
                )
            self.stars.append(Star(pos, color, radius))

    def draw(self, screen):
        for star in self.stars:
            star.draw(screen)

    def init_stars(self):
        self.stars = []
        star_params = random.choices(self.star_options, weights=self.weights, k=self.num_stars)
        for radius, color in star_params:            
            pos = (random.randint(0, self.screen_shape[0]), random.randint(0, self.screen_shape[1]))
            self.stars.append(Star(pos, color, radius))


#------------- GAME CLASS -----------------
class GameParams:
    lives = 5
    dronespawn_freq = 3000
    dronespawn_freq_ramp = 15
    black_holes = 2
    
    def __init__(self, level):
        self.level = level


class RelativityWars:
    fps = 60
    fpsClock = pygame.time.Clock()

    score = 0
    high_score = 0
    lives = 5
    level = 0

    sound_effects = True

    game_font = pygame.font.Font('assets/Aller_Rg.ttf', 32)
    game_font_small = pygame.font.Font('assets/Aller_Rg.ttf', 26)

    game_over_sound = pygame.mixer.Sound('assets/game-over.wav')
    game_over_10plus = pygame.mixer.Sound('assets/game-over-10plus.wav')
    game_over_20plus = pygame.mixer.Sound('assets/game-over-20plus.wav')
    game_over_50plus = pygame.mixer.Sound('assets/game-over-50plus.wav')

    start_screen = pygame.image.load('assets/start-screen.png').convert()

    black_hole_group = pygame.sprite.Group()
    torpedo_group = pygame.sprite.Group()
    enemy_torpedo_group = pygame.sprite.Group()

    pygame.mouse.set_visible(False)
    crosshair = Crosshair()

    DRONESPAWN = pygame.USEREVENT
    INCREASEDRONESPAWN = pygame.USEREVENT + 1
    drone_group = pygame.sprite.Group()

    game_active = False
    pygame.mixer.music.load('assets/game-music.wav')
    pygame.mixer.music.set_volume(0.3)

    def __init__(self, level=1, fighter=None, screen=screen, screen_shape=screen_shape):
        self.screen_shape = screen_shape
        self.screen = screen
        self.screen_width, self.screen_height = self.screen_shape
        self.screen_center = (self.screen_width / 2, self.screen_height / 2)
        self.START_SCREEN_OFFSET = tuple(int(x/2) for x in [self.screen_width - 350, self.screen_height - 480])

        self.get_level(level)

        if isinstance(fighter, Fighter):
            self.fighter = fighter
        else:
            self.fighter = Fighter(self.screen_shape, self.black_hole_group, self.torpedo_group, sound_effects=self.sound_effects)

    def get_level(self, level):
        self.level = level
        self.game_params = GameParams(level)

    def next_level(self):
        self.game_params = GameParams(self.level + 1)
        self.level += 1

    def setup_game(self):
        self.stars = Stars(self.screen_shape)
        self.dronespawn_freq = self.game_params.dronespawn_freq
        self.black_hole_group.empty()
        for _ in range(self.game_params.black_holes):
            pos = (random.randrange(200, self.screen_shape[0] - 200), random.randrange(200, self.screen_shape[1] - 200))
            size = random.randrange(50, 200)
            black_hole = BlackHole(pos, size=size)
            self.black_hole_group.add(black_hole)
        pygame.time.set_timer(self.DRONESPAWN, self.dronespawn_freq)
        pygame.time.set_timer(self.INCREASEDRONESPAWN, 3000)
        self.fighter.reset()

    def game_over(self):
        self.high_score = max([self.score, self.high_score])

        self.fighter.reset()
        self.drone_group.empty()
        self.torpedo_group.empty()
        self.enemy_torpedo_group.empty()
        pygame.time.set_timer(self.DRONESPAWN, 0)

    def score_display(self):
        score_surface = self.game_font.render(f'Score: {self.score}', True, (200, 200, 200))
        score_rect = score_surface.get_rect(center=(int(self.screen_shape[0] / 2), 30))
        self.screen.blit(score_surface, score_rect)

        lives_surface = self.game_font.render(f'Lives: {self.lives}', True, (170, 170, 170))
        lives_rect = lives_surface.get_rect(center=(int(self.screen_shape[0] / 2), 80))
        self.screen.blit(lives_surface, lives_rect)

    def is_mouse_over_button(self, button):
        button_coords = {'play': ((98, 281), (230, 341)),
                        'quit': ((12, 380), (91, 402)),
                        'music': ((148, 385), (159, 396)),
                        'effects': ((256, 385), (266, 396))}
        area = button_coords.get(button)
        area = tuple(np.array(point) + self.START_SCREEN_OFFSET for point in area)
        pos = pygame.mouse.get_pos()
        return area[0][0] < pos[0] < area[1][0] and area[0][1] < pos[1] < area[1][1]

    def play(self):
        pygame.mixer.music.play()
        self.setup_game()

        while True:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            if self.game_active:
                self.game_loop(events)
            else:
                self.start_screen_loop(events)
            pygame.display.flip()
            self.fpsClock.tick(self.fps)

    def game_loop(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.game_active = False
                    self.game_over()
                    break
                elif event.key == pygame.K_r:
                    self.fighter.reset()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.fighter.fire()
            elif event.type == self.DRONESPAWN:
                self.drone_group.add(Drone(self.screen_shape, self.black_hole_group, self.enemy_torpedo_group, sound_effects=self.sound_effects))
            elif event.type == self.INCREASEDRONESPAWN:
                self.dronespawn_freq = max([0, self.dronespawn_freq - self.game_params.dronespawn_freq_ramp])
                pygame.time.set_timer(self.DRONESPAWN, self.dronespawn_freq)
                for black_hole in self.black_hole_group:
                    black_hole.enlarge()
    
        fighter_collisions = pygame.sprite.spritecollide(self.fighter, self.enemy_torpedo_group, True)
        if fighter_collisions:
            self.lives -= 1
            if self.lives < 0:
                if self.sound_effects:
                    if self.score >= 50:
                        self.game_over_50plus.play()
                    elif self.score >= 20:
                        self.game_over_20plus.play()
                    elif self.score >= 10:
                        self.game_over_10plus.play()
                    else:
                        self.game_over_sound.play()
                self.game_active = False
                self.game_over()
            else:
                self.fighter.destroy(fighter_collisions[0].angle)

        hit_drones = pygame.sprite.groupcollide(self.drone_group, self.torpedo_group, False, True)
        if hit_drones:
            for drone, torpedos in hit_drones.items():
                self.score += 1
                drone.destroy(torpedos[0].angle)

        # Update
        self.fighter.update()
        self.crosshair.update()
        self.torpedo_group.update()
        self.enemy_torpedo_group.update()
        self.drone_group.update()
        self.stars.update()

        # Draw
        self.screen.fill((0, 0, 0))
        self.stars.draw(self.screen)
        self.score_display()
        self.black_hole_group.draw(self.screen)
        self.fighter.draw(self.screen)
        self.crosshair.draw(self.screen)
        self.torpedo_group.draw(self.screen)
        self.enemy_torpedo_group.draw(self.screen)
        self.drone_group.draw(self.screen)

    def start_screen_loop(self, events):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.is_mouse_over_button('quit'):
                    pygame.quit()
                    sys.exit()
                elif self.is_mouse_over_button('play'):
                    self.game_active = True
                    self.setup_game()
                elif self.is_mouse_over_button('music'):
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                    else:
                        pygame.mixer.music.play()
                elif self.is_mouse_over_button('effects'):
                    self.sound_effects = not self.sound_effects

        # Update
        self.crosshair.update()

        # Draw
        self.screen.fill((0, 0, 0))
        self.screen.blit(self.start_screen, (785, 300))

        score_render = self.game_font_small.render(f'Score: {self.score}', True, (255, 255, 255))
        score_render_rect = score_render.get_rect(center=tuple(x + y for x,y in zip(self.START_SCREEN_OFFSET, (175, 170))))
        self.screen.blit(score_render, score_render_rect)
        
        high_score_render = self.game_font_small.render('High Score', True, (255, 255, 255))
        high_score_render_rect = high_score_render.get_rect(center=tuple(x + y for x,y in zip(self.START_SCREEN_OFFSET, (175, 220))))
        self.screen.blit(high_score_render, high_score_render_rect)

        high_score_value_render = self.game_font_small.render(str(self.high_score), True, (255, 255, 255))
        high_score_value_render_rect = high_score_value_render.get_rect(center=tuple(x + y for x,y in zip(self.START_SCREEN_OFFSET, (175, 250))))
        self.screen.blit(high_score_value_render, high_score_value_render_rect)

        self.crosshair.draw(self.screen)


RelativityWars().play()
