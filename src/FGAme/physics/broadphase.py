# -*- coding: utf8 -*-

from FGAme.physics import CBBContact, AABBContact
from FGAme.physics import get_collision, get_collision_generic, CollisionError
from mathtools import shadow_y


class AbstractCollisionPhase(object):

    '''Base para BroadPhase e NarrowPhase'''

    __slots__ = ['world', '_data']

    def __init__(self, data=[], world=None):
        self.world = world
        self._data = []
        self._data.extend(data)

    def __iter__(self):
        for p in self._data:
            yield p

    def __call__(self, objects):
        self.update(objects)
        return self

    def __repr__(self):
        tname = type(self).__name__
        return '%s(%r)' % (tname, self._data)

    def update(self, objects):
        '''Atualiza a lista de pares utilizando a lista de objetos dada.'''

        raise NotImplementedError

    def objects(self):
        '''Iterador sobre a lista com todos os objetos obtidos na fase de
        colisão'''

        objs = set()
        for A, B in self._data:
            objs.add(A)
            objs.add(B)
        return iter(objs)

###############################################################################
#                               Broad phase
###############################################################################


class BroadPhase(AbstractCollisionPhase):

    '''Controla a broad-phase do loop de detecção de colisões de uma
    simulação.

    Um objeto do tipo BroadPhase possui uma interface simples que define dois
    métodos:

        bf.update(L) -> executa algoritmo em lista de objetos L
        iter(bf)     -> itera sobre todos os pares gerados no passo anterior

    '''

    __slots__ = []

    def pairs(self):
        '''Retorna a lista de pares encontradas por update'''

        return list(self._data)


class BroadPhaseAABB(BroadPhase):

    '''Implementa a broad-phase detectando todos os pares de AABBs que estão
    em contato no frame'''

    __slots__ = []

    def update(self, L):
        col_idx = 0
        objects = sorted(L, key=lambda obj: obj.xmin)
        self._data[:] = []

        # Os objetos estão ordenados. Este loop detecta as colisões da CBB e
        # salva o resultado na lista broad collisions
        for i, A in enumerate(objects):
            A_right = A.xmax
            A_dynamic = A.is_dynamic()

            for j in range(i + 1, len(objects)):
                B = objects[j]

                # Procura na lista enquanto xmin de B for menor que xmax de A
                B_left = B.xmin
                if B_left > A_right:
                    break

                # Não detecta colisão entre dois objetos estáticos/cinemáticos
                if not A_dynamic and not B.is_dynamic():
                    continue
                if A.is_sleep and B.is_sleep:
                    continue

                # Testa a colisão entre as AABBs
                if shadow_y(A, B) <= 0:
                    continue

                # Adiciona à lista de colisões grosseiras
                col_idx += 1
                self._data.append(AABBContact(A, B))


class BroadPhaseCBB(BroadPhase):

    '''Implementa a broad-phase detectando todos os pares de CBBs que estão
    em contato no frame'''

    __slots__ = []

    def update(self, L):
        col_idx = 0
        objects = sorted(L, key=lambda obj: obj.pos.x - obj.cbb_radius)
        self._data[:] = []

        # Os objetos estão ordenados. Este loop detecta as colisões da CBB e
        # salva o resultado na lista broad collisions
        for i, A in enumerate(objects):
            A_radius = A.cbb_radius
            A_right = A.pos.x + A_radius
            A_dynamic = A.is_dynamic()

            for j in range(i + 1, len(objects)):
                B = objects[j]
                B_radius = B.cbb_radius

                # Procura na lista enquanto xmin de B for menor que xmax de A
                B_left = B._pos.x - B_radius
                if B_left > A_right:
                    break

                # Não detecta colisão entre dois objetos estáticos/cinemáticos
                if not A_dynamic and not B.is_dynamic():
                    continue
                if A.is_sleep and B.is_sleep:
                    continue

                # Testa a colisão entre os círculos de contorno
                if (A.pos - B.pos).norm() > A_radius + B_radius:
                    continue

                # Adiciona à lista de colisões grosseiras
                col_idx += 1
                self._data.append(CBBContact(A, B))


###############################################################################
#                               Narrow phase
###############################################################################
class NarrowPhase(AbstractCollisionPhase):

    '''Implementa a fase fina da detecção de colisão'''

    __slots__ = []

    def update(self, broad_cols):
        '''Escaneia a lista de colisões grosseiras e detecta quais delas
        realmente aconteceram'''

        # Detecta colisões e atualiza as listas internas de colisões de
        # cada objeto
        self._data = cols = []

        for A, B in broad_cols:
            col = self.get_collision(A, B)

            if col is not None:
                col.world = self.world
                cols.append(col)

    def get_collision(self, A, B):
        '''Retorna a colisão entre os objetos A e B depois que a colisão AABB
        foi detectada'''

        try:
            return get_collision(A, B)
        except CollisionError:
            pass

        # Colisão não definida. Primeiro tenta a colisão simétrica e registra
        # o resultado caso bem sucedido. Caso a colisão simétrica também não
        # seja implementada, define a colisão como uma aabb
        try:
            col = get_collision(B, A)
            if col is None:
                return
            col.normal *= -1
        except CollisionError:
            get_collision[type(A), type(B)] = get_collision_generic
            get_collision[type(B), type(A)] = get_collision_generic
            return get_collision_generic(A, B)
        else:
            direct = get_collision.get_implementation(type(B), type(A))

            def inverse(A, B):
                '''Automatically created collision for A, B from the supported
                collision B, A'''
                col = direct(B, A)
                if col is not None:
                    return col.swapped()

            get_collision[type(A), type(B)] = inverse
            return col

    def get_groups(self, cols=None):
        '''Retorna uma lista com todos os grupos de colisões fechados'''

        if cols is None:
            cols = self

        meta_cols = BroadPhaseAABB(cols)
        print(meta_cols)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
