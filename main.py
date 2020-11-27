import pygame
import sys
import math
import numpy as np
import random
import time
import json
from screeninfo import get_monitors
from scipy.stats import skewnorm


pygame.mixer.init()
pygame.init()

monitor = get_monitors()[0]
screen_shape = (monitor.width, monitor.height)
screen = pygame.display.set_mode(screen_shape, pygame.FULLSCREEN)


def blit_alpha(target, source, opacity):
    x = source.rect.center[0]
    y = source.rect.center[1]
    surface = source.image
    temp = pygame.Surface((surface.get_width(), surface.get_height())).convert()
    temp.blit(target, (-x, -y))
    temp.blit(surface, (0, 0))
    temp.set_alpha(opacity)        
    target.blit(temp, (x, y))


class RWSprite(pygame.sprite.Sprite):
    GRAVITATIONAL_CONSTANT = 180
    MAX_GRAVITY = 20

    def __init__(self, pos, velocity, game):
        super().__init__()
        self.game = game
        self.pos = pos

    def calculate_gravity(self):
        vector = np.array([0., 0.])
        for black_hole in self.game.black_hole_group:
            relative_pos = self.pos - black_hole.pos
            angle = self.get_angle_from_vector(relative_pos)
            distance = math.sqrt(relative_pos[0]**2 + relative_pos[1]**2)
            vector += np.array([-self.GRAVITATIONAL_CONSTANT / math.copysign(distance**1.1, rel) if distance != 0 else 0 for rel in relative_pos])
        net_gravity = math.sqrt(vector[0]**2 + vector[1]**2)
        if net_gravity > self.MAX_GRAVITY:
            vector *= self.MAX_GRAVITY / net_gravity
        return vector

    @staticmethod
    def get_angle_from_vector(vector):
        return math.atan(vector[1] / vector[0]) if vector[0] != 0 else math.pi / 2

    def center_to_pos(self):
        self.rect.center = [int(p) for p in self.pos]

    def wrap_pos(self):
        if self.pos[0] < 0:
            self.pos = (self.game.screen_shape[0], self.game.screen_shape[1] - self.pos[1])
        elif self.pos[0] > self.game.screen_shape[0]:
            self.pos = (0, self.game.screen_shape[1] - self.pos[1])
        if self.pos[1] < 0:
            self.pos = (self.game.screen_shape[0] - self.pos[0], self.game.screen_shape[1])
        elif self.pos[1] > self.game.screen_shape[1]:
            self.pos = (self.game.screen_shape[0] - self.pos[0], 0)

    def kill_if_offscreen(self):
        if not 0 <= self.rect.center[0] <= self.game.screen_shape[0] or not 0 <= self.rect.center[1] <= self.game.screen_shape[1]:
            self.kill()

    def kill_if_in_black_hole(self):
        if pygame.sprite.spritecollide(self, self.game.black_hole_group, False):
            self.kill()
    
    @staticmethod
    def hypotenuse(vector):
        return math.sqrt(vector[0]**2 + vector[1]**2)


class DroneBase(RWSprite):
    torpedo_sound = pygame.mixer.Sound('assets/torpedo.wav')
    speed = 3
    drag = 0.1
    death_time = None

    def __init__(self, game):
        self.game = game
        self.random_init()
        super().__init__(self.pos, self.velocity, game)
        self.init_time = time.time()
        self.last_fired_time = self.init_time

    def random_init(self):
        if random.choice([True, False]):
            self.pos = np.array([random.choice([0, self.game.screen_shape[0]]), random.randrange(0, self.game.screen_shape[1])], dtype='float64')
            self.velocity = np.array([self.speed * (1 if self.pos[0] == 0 else -1), random.choice([-3, 3])], dtype='float64')
        else:
            self.pos = np.array([random.randrange(0, self.game.screen_shape[0]), random.choice([0, screen_shape[1]])], dtype='float64')
            self.velocity = np.array([random.choice([-3, 3]), self.speed * (1 if self.pos[1] == 0 else -1)], dtype='float64')
        self.rect = self.image.get_rect()
        self.center_to_pos()
    
    def update(self):
        self.accelerate()
        self.pos += self.velocity
        self.center_to_pos()
        self.kill_if_offscreen()
        self.kill_if_in_black_hole()

    def accelerate(self):
        gravity = self.calculate_gravity()
        self.velocity = (self.velocity + gravity) * (1 - self.drag)

    def destroy(self, angle):
        if self.death_time is None:
            self.image = pygame.transform.rotate(self.image_death.copy(), angle)
            if self.game.sound_effects:
                self.sound_death.play()
            self.death_time = time.time()


class BlackHole(RWSprite):
    raw_image = pygame.image.load('assets/black_hole.png').convert()
    speed = 0.5

    def __init__(self, pos, game, size=None):
        self.direction = random.randrange(0, 7)
        self.pos = pos
        super().__init__(self.pos, self.velocity, game)
        self.image = self.raw_image.copy()
        self.size = size
        if size is not None:
            self.image = pygame.transform.scale(self.image, (size, size))
        self.rect = self.image.get_rect()
        self.center_to_pos()
        self.path_radius, self.path_arc = self.random_arc()
        self.arc_traversed = 0

    @property
    def gravity(self):
        return self.size / 100

    @property
    def velocity(self):
        return np.array([math.cos(self.direction) * self.speed, math.sin(self.direction) * self.speed])

    def update(self):
        self.direction = self.next_direction()
        self.pos = self.pos + self.velocity
        self.wrap_pos()
        self.center_to_pos()

    def random_arc(self):
        path_radius = random.randint(50, self.game.screen_shape[1] / 2)
        path_arc = random.randrange(1, 7) * random.choice([-1, 1]) * path_radius
        return path_radius, path_arc

    def next_direction(self):
        if self.arc_traversed >= abs(self.path_arc):
            self.path_radius, self.path_arc = self.random_arc()
            self.arc_traversed = 0
        self.arc_traversed += self.speed
        next_dir = 1.0 * self.speed / np.copysign(self.path_radius,  self.path_arc) + self.direction
        return next_dir

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
        directions[direction]['image_shielded'] = pygame.image.load(f'assets/fighter_{direction}_shielded.png').convert_alpha()
    torpedo_sound = pygame.mixer.Sound('assets/torpedo.wav')

    death_image = pygame.image.load('assets/fighter-death.png')
    death_sound = pygame.mixer.Sound('assets/fighter-death.wav')
    death_time = None

    reset_time = None
    reset_duration = 2
    reset_active = True
    reset_alpha = 0
    reset_alpha_vel = -10

    shields = False
    shield_up_sound = pygame.mixer.Sound('assets/shield-up.wav')
    shield_down_sound = pygame.mixer.Sound('assets/shield-down.wav')

    boost_acceleration = 3
    boost_duration = 0.25
    boost_last_used = 0
    boost_cooldown = 10
    boost_active = False
    boost_sound = pygame.mixer.Sound('assets/boost.wav')

    zerog_torpedos = True
    zerog_clipsize = 20
    zerog_fired = 0

    initial_pos = np.array([100, 100])
    pos = initial_pos
    drag = 0.05
    velocity = np.array([0., 0.])  # speed x, speed y
    direction = 'right'  # degrees
    acceleration = 1
    image = directions[direction]['image']
    rect = image.get_rect(center=initial_pos)

    def __init__(self, game):
        super().__init__(self.pos, self.velocity, game)

    @property
    def boost_available(self):
        return time.time() - self.boost_last_used > self.boost_cooldown

    def boost(self):
        if self.boost_available:
            self.boost_active = True
            self.boost_last_used = time.time()
            if self.game.sound_effects:
                self.boost_sound.play()

    def update_direction(self):
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

    def move(self):
        new_pos = self.pos + self.velocity
        for i in range(2):
            if new_pos[i] < 0:
                new_pos[i] = 0
                if self.velocity[i] <= 0:
                    self.velocity[i] = 0
                self.velocity[i] = 0
            elif new_pos[i] > self.game.screen_shape[i]:
                new_pos[i] = self.game.screen_shape[i]
                if self.velocity[i] >= 0:
                    self.velocity[i] = 0
        self.pos = new_pos
        self.center_to_pos()

    def accelerate(self):
        gravity = self.calculate_gravity()
        accel = self.boost_acceleration if self.boost_active else self.acceleration
        if self.death_time is None:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w] or keys[pygame.K_a] or keys[pygame.K_s] or keys[pygame.K_d]:
                angle = self.directions[self.direction]['angle']
                self.velocity = [math.cos(angle) * accel + self.velocity[0],
                                math.sin(angle) * accel + self.velocity[1]]
        self.velocity = (self.velocity + gravity) * (1 - self.drag)

    def get_powerup(self, powerup):
        if powerup.power == 'shield' and self.shields == False:
            self.shields = True
            if self.game.sound_effects:
                self.shield_up_sound.play()
        if powerup.power == 'zerog_torpedo':
            self.zerog_torpedos = True
            self.zerog_fired = 0
            if self.game.sound_effects:
                self.shield_up_sound.play()
            self.game.crosshair.set_skin('zerog')
        powerup.kill()

    def update(self):
        if self.death_time:
            if time.time() > self.death_time + 1:
                self.reset()
        else:
            self.update_direction()
            if self.shields:
                self.image = self.directions[self.direction]['image_shielded']
            else:
                self.image = self.directions[self.direction]['image']

        # update boost
        if self.boost_active and time.time() - self.boost_last_used > self.boost_duration:
            self.boost_active = False
        # update reset
        if self.reset_active and time.time() - self.reset_time > self.reset_duration:
            self.reset_active = False
            self.reset_alpha, self.reset_alpha_vel = 0, -10
        self.accelerate()
        self.move()

    def draw(self, screen):
        if self.reset_active:
            if not (0 < self.reset_alpha < 180):
                self.reset_alpha_vel *= -1
            self.reset_alpha += self.reset_alpha_vel
            # self.reset_alpha = 128
            blit_alpha(screen, self, self.reset_alpha)
        else:
            screen.blit(self.image, self.rect)

    def reset(self):
        self.direction = 'right'
        self.velocity = [0, 0]
        self.rect.center = self.initial_pos
        self.death_time = None
        self.reset_time = time.time()
        self.reset_active = True
    
    def fire(self):
        if self.death_time is None:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            init_x, init_y = self.rect.center
            delta_x = mouse_x - init_x
            delta_y = init_y - mouse_y
            angle = math.degrees(math.atan(delta_y / delta_x)) if delta_x != 0 else 0
            if delta_x < 0:
                angle += 180
            if self.zerog_torpedos:
                skin = 'zerog'
                self.zerog_fired += 1
                if self.zerog_fired >= self.zerog_clipsize:
                    self.zerog_torpedos = False
                    self.game.crosshair.set_skin(None)
            else:
                skin = None
            self.game.torpedo_group.add(Torpedo((init_x, init_y), angle, self.game, skin=skin))
            if self.game.sound_effects:
                self.torpedo_sound.play()

    def destroy(self, angle):
        if self.shields == True:
            self.shields = False
            if self.game.sound_effects:
                self.shield_down_sound.play()
        elif self.death_time is None:
            self.image = pygame.transform.rotate(self.death_image.copy(), angle)
            if self.game.sound_effects:
                self.death_sound.play()
            self.death_time = time.time()


class Crosshair(pygame.sprite.Sprite):
    raw_image = pygame.image.load('assets/crosshair.png').convert_alpha()
    image = raw_image.copy()
    rect = image.get_rect()
    skin_names = ('zerog', )
    skins = {skin: pygame.image.load(f'assets/crosshair-{skin}.png').convert_alpha() for skin in skin_names}

    def __init__(self):
        super().__init__()

    def update(self):
        self.rect.center = pygame.mouse.get_pos()

    def draw(self, screen):
        screen.blit(self.image, self.rect)

    def set_skin(self, skin):
        if skin is None:
            self.image = self.raw_image.copy()
        else:
            self.image = self.skins.get(skin).copy()


class Torpedo(RWSprite):
    raw_image = pygame.image.load('assets/torpedo.png').convert_alpha()
    skin_names = ('zerog', )
    skins = {skin: pygame.image.load(f'assets/torpedo_{skin}.png').convert_alpha() for skin in skin_names}

    def __init__(self, pos, angle, game, speed=20, skin=None):
        self.skin = skin
        if skin is not None:
            self.raw_image = self.skins.get(skin).copy()
        if skin == 'zerog':
            speed = 40
        self.image = self.raw_image.copy()
        
        self.speed = speed
        self.pos = pos
        velocity_x = math.cos(math.radians(angle)) * self.speed
        velocity_y = -math.sin(math.radians(angle)) * self.speed
        self.velocity = np.array([velocity_x, velocity_y])
        
        super().__init__(self.pos, self.velocity, game)
        self.angle = angle
        self.image = pygame.transform.rotate(self.image, self.angle)
        self.rect = self.image.get_rect()
        self.center_to_pos()

    def update(self):
        init_angle = self.angle
        if self.skin == 'zerog':
            gravity = (0, 0)
        else:
            gravity = self.calculate_gravity()
        self.velocity = self.velocity + gravity
        self.pos += self.velocity
        self.center_to_pos()
        self.angle = math.degrees(math.atan(-self.velocity[1] / self.velocity[0])) if self.velocity[0] != 0 else 90
        if self.velocity[0] < 0:
            self.angle += 180
        self.image = pygame.transform.rotate(self.raw_image.copy(), self.angle)
        self.kill_if_offscreen()
        self.kill_if_in_black_hole()


class EnemyFighter(DroneBase):
    raw_image = pygame.image.load('assets/fighter_red_right.png').convert_alpha()
    image = raw_image.copy()
    image_death = pygame.image.load('assets/fighter-death.png')
    sound_death = pygame.mixer.Sound('assets/fighter-death.wav')
    speed = 1
    acceleration = 1

    def __init__(self, game):
        super().__init__(game)

    def accelerate(self):
        gravity = self.calculate_gravity()
        rel_pos = self.pos - self.game.fighter.pos
        unit_gravity = gravity / self.hypotenuse(gravity)
        unit_rel_pos = rel_pos / self.hypotenuse(rel_pos)
        acc = rel_pos, - gravity
        unit_acc = acc / self.hypotenuse(acc)
        unit_acc = unit_rel_pos
        self.velocity = [self.acceleration * a + v for a,v in zip(unit_acc, self.velocity)]
        # print(gravity, unit_acc, self.pos, self.velocity)

    def _(self):
        gravity = self.calculate_gravity()
        unit_gravity = [g / math.sqrt(gravity[0]**2 + gravity[1]**2) for g in gravity]
        velocity_max_escape = self.velocity + gravity - unit_gravity * self.acceleration

    def update(self):
        self.accelerate()
        self.pos = self.pos + self.velocity
        self.wrap_pos()
        self.center_to_pos()
        angle = self.get_angle_from_vector(self.velocity)
        self.image = pygame.transform.rotate(self.raw_image.copy(), angle)


class Drone(DroneBase):
    sound_death = pygame.mixer.Sound('assets/drone-death.wav')
    image = pygame.image.load('assets/drone.png').convert_alpha()
    image_death = pygame.image.load('assets/drone-death.png').convert_alpha()
    speed = 8

    def __init__(self, game):
        super().__init__(game)

    def update(self):
        super().update()
        if time.time() > self.init_time + 10:
            self.kill()
        elif time.time() > self.last_fired_time + 1.5 and self.death_time is None:
            for angle in np.arange(0, 7) * 45:
                self.game.enemy_torpedo_group.add(Torpedo(self.rect.center, angle, self.game, speed=10))
            if self.game.sound_effects:
                self.torpedo_sound.play()
            self.last_fired_time = time.time()
        elif self.death_time:
            if time.time() > self.death_time + 0.5:
                self.kill()


class Powerup(DroneBase):
    images = {
        'shield': pygame.image.load('assets/shield_orb.png').convert_alpha(),
        'zerog_torpedo': pygame.image.load('assets/zerog_torpedo_orb.png').convert_alpha(),
    }
    speed = 6

    def __init__(self, power, game):
        self.image = self.images.get(power)
        super().__init__(game)
        self.power = power
        self.random_init()

    def update(self):
        super().update()
        if time.time() > self.init_time + 10:
            self.kill()


class Star:
    def __init__(self, pos, color, radius):
        self.pos = pos
        self.color = color
        self.radius = radius

    def draw(self, screen):
        posint = tuple(map(int, self.pos))
        # print(self.pos, posint)
        pygame.draw.circle(screen, self.color, posint, self.radius)


class Stars:
    colors = ((x, x, x) for x in (80, 120, 145, 180, 225))
    star_options = tuple(zip((1, 1, 2, 2, 3), (colors)))
    weights = (60, 30, 15, 7, 3)
    num_stars = 500
    velocity = np.array([-.2, .1])

    def __init__(self, screen_shape):
        self.screen_shape = screen_shape
        self.init_stars()

    def update(self):
        num_new = 0
        for i in reversed(range(len(self.stars))):
            star = self.stars[i]
            # offset stars
            star.pos += self.velocity
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
                pos = np.array([
                    random.random() * self.screen_shape[0],
                    0 if self.velocity[1] > 0 else self.screen_shape[1]
                ])
            else:
                pos = np.array([
                    0 if self.velocity[0] > 0 else self.screen_shape[0],
                    random.random() * self.screen_shape[1]
                ])
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
    dronespawn_freq = 2000
    dronespawn_freq_ramp = 15
    black_holes = 2
    black_hole_total_size = 350
    powerupspawn_freq = 10000
    nextlevel_freq = 1 * 60 * 1000
    
    def __init__(self, level):
        self.level = level
        self.black_holes += level - 1
        self.powerupspawn_freq -= 1000 * (level - 1)
        self.dronespawn_freq = int(self.dronespawn_freq * 0.8**(level - 1))
        self.dronespawn_freq_ramp += 10 * (level - 1)


class RelativityWars:
    fps = 60
    fpsClock = pygame.time.Clock()

    score = 0
    lives = 5
    level = 0

    sound_effects = True

    game_font = pygame.font.Font('assets/Aller_Rg.ttf', 32)
    game_font_small = pygame.font.Font('assets/Aller_Rg.ttf', 26)

    game_over_sound = pygame.mixer.Sound('assets/game-over.wav')
    game_over_10plus = pygame.mixer.Sound('assets/game-over-10plus.wav')
    game_over_20plus = pygame.mixer.Sound('assets/game-over-20plus.wav')
    game_over_50plus = pygame.mixer.Sound('assets/game-over-50plus.wav')

    checkmark = pygame.image.load('assets/checkmark.png')

    start_screen = pygame.image.load('assets/start-screen.png').convert()
    next_level_images = [pygame.image.load(f'assets/next_level_{i + 1}.png').convert_alpha() for i in range(3)]
    boost_bar_layers =  [pygame.image.load('assets/boost-bar-background.png').convert_alpha(),
                         pygame.image.load('assets/boost-bar-foreground.png').convert_alpha()]

    black_hole_group = pygame.sprite.Group()
    torpedo_group = pygame.sprite.Group()
    enemy_torpedo_group = pygame.sprite.Group()
    powerup_group = pygame.sprite.Group()
    enemy_fighter_group = pygame.sprite.Group()

    pygame.mouse.set_visible(False)
    crosshair = Crosshair()

    DRONESPAWN = pygame.USEREVENT
    INCREASEDRONESPAWN = pygame.USEREVENT + 1
    POWERUPSPAWN = pygame.USEREVENT + 2
    NEXTLEVEL = pygame.USEREVENT + 3
    next_level_transition = True
    next_level_image_scale = 0.1
    next_level_transition_start_time = 0
    level_start_time = 0
    drone_group = pygame.sprite.Group()

    game_active = False
    pygame.mixer.music.load('assets/game-music.wav')
    pygame.mixer.music.set_volume(0.3)

    def __init__(self, level=1, fighter=None, screen=screen, screen_shape=screen_shape):
        self.screen_shape = screen_shape
        self.screen = screen
        self.screen_width, self.screen_height = self.screen_shape
        self.screen_center = (int(self.screen_width / 2), int(self.screen_height / 2))
        self.START_SCREEN_OFFSET = tuple(int(x/2) for x in [self.screen_width - 350, self.screen_height - 480])
        self.load_vars()  # loads high_score

        self.boost_bar_pos = (self.screen_shape[0] - 320, self.screen_shape[1] - 50)

        self.get_level(level)

        if isinstance(fighter, Fighter):
            self.fighter = fighter
        else:
            self.fighter = Fighter(self)

    def get_level(self, level):
        self.level = level
        self.game_params = GameParams(level)

    def next_level(self):
        self.game_params = GameParams(self.level + 1)
        self.level += 1

    def setup_game(self):
        self.stars = Stars(self.screen_shape)
        self.dronespawn_freq = self.game_params.dronespawn_freq
        self.powerupspawn_freq = self.game_params.powerupspawn_freq
        self.black_hole_group.empty()
        self.torpedo_group.empty()
        self.enemy_torpedo_group.empty()
        self.powerup_group.empty()
        self.drone_group.empty()
        self.enemy_torpedo_group.empty()
        
        # black hole generation
        rand = np.array([random.random() + 1 for _ in range(self.game_params.black_holes)])
        sizes = self.game_params.black_hole_total_size / sum(rand) * rand
        sizes = [int(s) for s in sizes]
        for i in range(self.game_params.black_holes):
            pos = np.array([random.randrange(200, self.screen_shape[0] - 200), random.randrange(200, self.screen_shape[1] - 200)])
            black_hole = BlackHole(pos, self, size=sizes[i])
            self.black_hole_group.add(black_hole)

        pygame.time.set_timer(self.DRONESPAWN, self.dronespawn_freq)
        pygame.time.set_timer(self.INCREASEDRONESPAWN, 3000)
        pygame.time.set_timer(self.POWERUPSPAWN, self.powerupspawn_freq)
        pygame.time.set_timer(self.NEXTLEVEL, self.game_params.nextlevel_freq)
        self.fighter.reset()
        self.level_start_time = time.time()
        self.lives = 5
        self.fighter.shields = False
        self.fighter.zerog_torpedos = False
        self.fighter.zerog_fired = 0

        # self.enemy_fighter_group.add(EnemyFighter(self))

    def game_over(self):
        self.high_score = max([self.score, self.high_score])
        self.get_level(1)

    def score_display(self):
        score_surface = self.game_font.render(f'Score: {self.score}', True, (200, 200, 200))
        score_rect = score_surface.get_rect(center=(int(self.screen_shape[0] / 2), 30))
        self.screen.blit(score_surface, score_rect)

        lives_surface = self.game_font.render(f'Lives: {self.lives}', True, (170, 170, 170))
        lives_rect = lives_surface.get_rect(center=(int(self.screen_shape[0] / 2), 80))
        self.screen.blit(lives_surface, lives_rect)

        level_surface = self.game_font.render(f'Level {self.level}', True, (170, 170, 170))
        level_rect = level_surface.get_rect(center=(self.screen_shape[0] - 240, 30))
        self.screen.blit(level_surface, level_rect)

        next_level_secs = self.game_params.nextlevel_freq / 1000 - (time.time() - self.level_start_time)
        level_time_surface = self.game_font_small.render(f'Next Level {math.floor(next_level_secs / 60)}:{int(next_level_secs % 60):02d}', True, (170, 170, 170))
        level_time_rect = level_time_surface.get_rect(center=(self.screen_shape[0] - 202, 80))
        self.screen.blit(level_time_surface, level_time_rect)

        self.screen.blit(self.boost_bar_layers[0], self.boost_bar_pos)
        boost_progress = (time.time() - self.fighter.boost_last_used) / self.fighter.boost_cooldown
        if boost_progress >= 1:
            boost_color = (53, 172, 240)
            boost_progress = 1
        else:
            boost_color =  (86, 138, 168)
        boost_rect = pygame.Rect(self.boost_bar_pos[0] + 158,
                                 self.boost_bar_pos[1] + 11,
                                 int(boost_progress * 130),
                                 20)
        pygame.draw.rect(self.screen, boost_color, boost_rect)
        self.screen.blit(self.boost_bar_layers[1], self.boost_bar_pos)

        if self.fighter.zerog_torpedos:
            rounds = self.fighter.zerog_clipsize - self.fighter.zerog_fired
            x = self.screen_shape[0] - 35
            y = self.screen_shape[1] - 70
            t = pygame.transform.rotate(Torpedo.raw_image, math.pi / 4)
            for i in range(rounds):
                if i < 10:
                    self.screen.blit(Torpedo.raw_image, (x - i * 30, y))
                else:
                    self.screen.blit(Torpedo.raw_image, (x - (i - 10) * 30, y - 15))

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
        # pygame.mixer.music.play()
        self.setup_game()

        while True:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.exit()
            if not self.game_active:
                self.start_screen_loop(events)
            elif self.next_level_transition:
                self.next_level_transition_loop()
            elif self.game_active:
                self.game_loop(events)
            pygame.display.flip()
            self.fpsClock.tick(self.fps)

    def load_vars(self):
        with open('vars.json', 'r') as f:
            myvars = json.loads(f.read())
            self.high_score = myvars.get('high_score') or 0

    def write_vars(self):
        with open('vars.json', 'w') as f:
            f.write(json.dumps({'high_score': self.high_score}))

    def exit(self):
        self.write_vars()
        pygame.quit()
        sys.exit()

    def game_loop(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.game_active = False
                    self.game_over()
                    break
                elif event.key == pygame.K_r:
                    self.fighter.reset()
                elif event.key == pygame.K_LSHIFT:
                    self.fighter.boost()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.fighter.fire()
            elif event.type == self.DRONESPAWN:
                self.drone_group.add(Drone(self))
            elif event.type == self.INCREASEDRONESPAWN:
                self.dronespawn_freq = max([0, self.dronespawn_freq - self.game_params.dronespawn_freq_ramp])
                pygame.time.set_timer(self.DRONESPAWN, self.dronespawn_freq)
                for black_hole in self.black_hole_group:
                    black_hole.enlarge()
            elif event.type == self.POWERUPSPAWN:
                power = random.choice(['shield', 'zerog_torpedo'])
                self.powerup_group.add(Powerup(power, self))
            elif event.type == self.NEXTLEVEL:
                self.next_level_transition_start_time = time.time()
                self.next_level_transition = True
                self.get_level(self.level + 1)
    
        if not self.fighter.reset_active:
            fighter_collisions = pygame.sprite.spritecollide(self.fighter, self.enemy_torpedo_group, True)
            if fighter_collisions:
                if not self.fighter.shields:
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
                if drone.death_time is None:
                    self.score += 1
                    drone.destroy(torpedos[0].angle)

        powerup_collisions = pygame.sprite.spritecollide(self.fighter, self.powerup_group, False)
        if powerup_collisions:
            for powerup in powerup_collisions:
                self.fighter.get_powerup(powerup)

        # Update
        self.fighter.update()
        self.black_hole_group.update()
        self.crosshair.update()
        self.torpedo_group.update()
        self.enemy_torpedo_group.update()
        self.drone_group.update()
        self.powerup_group.update()
        self.stars.update()
        self.enemy_fighter_group.update()

        # Draw
        self.screen.fill((0, 0, 0))
        self.stars.draw(self.screen)
        self.black_hole_group.draw(self.screen)
        self.drone_group.draw(self.screen)
        self.powerup_group.draw(self.screen)
        self.fighter.draw(self.screen)
        self.crosshair.draw(self.screen)
        self.enemy_fighter_group.draw(self.screen)
        self.torpedo_group.draw(self.screen)
        self.enemy_torpedo_group.draw(self.screen)
        self.score_display()

    def start_screen_loop(self, events):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.is_mouse_over_button('quit'):
                    self.exit()
                elif self.is_mouse_over_button('play'):
                    self.next_level_transition = True
                    self.next_level_transition_start_time = time.time()
                    self.game_active = True
                    self.score = 0
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

        if self.sound_effects:
            self.screen.blit(self.checkmark, (self.START_SCREEN_OFFSET[0] + 256, self.START_SCREEN_OFFSET[1] + 375))
        if pygame.mixer.music.get_busy():
            self.screen.blit(self.checkmark, (self.START_SCREEN_OFFSET[0] + 148, self.START_SCREEN_OFFSET[1] + 375))
        self.crosshair.draw(self.screen)

    def next_level_transition_loop(self):
        if self.next_level_transition_start_time > time.time() - 1.5:
            self.screen.fill((0, 0, 0))
            self.stars.draw(self.screen)
            dims = tuple(int(self.next_level_image_scale * d) for d in (350, 172))
            try:
                image = self.next_level_images[self.level - 1]
            except IndexError:
                image = self.next_level_images[-1]
            image = pygame.transform.scale(image, dims)
            rect = image.get_rect(center=self.screen_center)
            self.screen.blit(image, rect)

            if self.next_level_image_scale <= 1:
                self.next_level_image_scale += 0.1
        else:
            self.next_level_transition = False
            self.next_level_transition_start_time = 0
            self.next_level_image_scale = 0.1
            self.setup_game()

RelativityWars().play()
